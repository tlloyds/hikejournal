import Foundation
import SQLite3

public enum OfflineStoreError: Error, Equatable, LocalizedError, Sendable {
    case openFailed(path: String, message: String)
    case sqlite(code: Int32, message: String, statement: String)
    case migrationTooNew(found: Int, supported: Int)
    case invalidStoredValue(table: String, column: String, value: String)
    case databaseClosed

    public var errorDescription: String? {
        switch self {
        case let .openFailed(path, message):
            "Could not open the offline database at \(path): \(message)"
        case let .sqlite(code, message, statement):
            "SQLite error \(code) while running \(statement): \(message)"
        case let .migrationTooNew(found, supported):
            "Offline database version \(found) is newer than supported version \(supported)."
        case let .invalidStoredValue(table, column, value):
            "Invalid value \(value) in \(table).\(column)."
        case .databaseClosed:
            "The offline database is closed."
        }
    }
}

final class SQLiteConnection {
    private(set) var handle: OpaquePointer?
    private let path: String

    init(path: String) throws {
        self.path = path
        try open()
    }

    private func open() throws {
        guard handle == nil else { return }
        var opened: OpaquePointer?
        let result = sqlite3_open_v2(
            path,
            &opened,
            SQLITE_OPEN_CREATE | SQLITE_OPEN_READWRITE | SQLITE_OPEN_FULLMUTEX,
            nil
        )
        guard result == SQLITE_OK, let opened else {
            let message = opened.map { String(cString: sqlite3_errmsg($0)) } ?? "unknown error"
            if let opened {
                sqlite3_close_v2(opened)
            }
            throw OfflineStoreError.openFailed(path: path, message: message)
        }
        handle = opened
        sqlite3_extended_result_codes(opened, 1)

        do {
            try execute("PRAGMA foreign_keys = ON")
            try execute("PRAGMA journal_mode = WAL")
            try execute("PRAGMA synchronous = FULL")
            try execute("PRAGMA busy_timeout = 5000")
            try execute("PRAGMA wal_autocheckpoint = 1000")
        } catch {
            close()
            throw error
        }
    }

    deinit {
        close()
    }

    func close() {
        guard let handle else { return }
        sqlite3_close_v2(handle)
        self.handle = nil
    }

    func execute(_ sql: String) throws {
        try ensureOpen()
        guard let handle else { throw OfflineStoreError.databaseClosed }
        var errorPointer: UnsafeMutablePointer<CChar>?
        let result = sqlite3_exec(handle, sql, nil, nil, &errorPointer)
        guard result == SQLITE_OK else {
            let message: String
            if let errorPointer {
                message = String(cString: errorPointer)
                sqlite3_free(errorPointer)
            } else {
                message = String(cString: sqlite3_errmsg(handle))
            }
            throw OfflineStoreError.sqlite(
                code: sqlite3_extended_errcode(handle),
                message: message,
                statement: sql
            )
        }
    }

    func prepare(_ sql: String) throws -> SQLiteStatement {
        try ensureOpen()
        guard let handle else { throw OfflineStoreError.databaseClosed }
        var statement: OpaquePointer?
        let result = sqlite3_prepare_v2(handle, sql, -1, &statement, nil)
        guard result == SQLITE_OK, let statement else {
            throw error(statement: sql)
        }
        return SQLiteStatement(connection: self, handle: statement, sql: sql)
    }

    private func ensureOpen() throws {
        if handle == nil {
            try open()
        }
    }

    func transaction<T>(_ body: () throws -> T) throws -> T {
        try execute("BEGIN IMMEDIATE")
        do {
            let result = try body()
            try execute("COMMIT")
            return result
        } catch {
            try? execute("ROLLBACK")
            throw error
        }
    }

    func error(statement: String) -> OfflineStoreError {
        guard let handle else { return .databaseClosed }
        return .sqlite(
            code: sqlite3_extended_errcode(handle),
            message: String(cString: sqlite3_errmsg(handle)),
            statement: statement
        )
    }
}

final class SQLiteStatement {
    private unowned let connection: SQLiteConnection
    private var handle: OpaquePointer?
    let sql: String

    init(connection: SQLiteConnection, handle: OpaquePointer, sql: String) {
        self.connection = connection
        self.handle = handle
        self.sql = sql
    }

    deinit {
        if let handle {
            sqlite3_finalize(handle)
        }
    }

    func bind(_ value: String?, at index: Int32) throws {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        let result: Int32
        if let value {
            result = sqlite3_bind_text(handle, index, value, -1, sqliteTransient)
        } else {
            result = sqlite3_bind_null(handle, index)
        }
        try check(result)
    }

    func bind(_ value: Data?, at index: Int32) throws {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        let result: Int32
        if let value {
            result = value.withUnsafeBytes { bytes in
                sqlite3_bind_blob(handle, index, bytes.baseAddress, Int32(bytes.count), sqliteTransient)
            }
        } else {
            result = sqlite3_bind_null(handle, index)
        }
        try check(result)
    }

    func bind(_ value: Int?, at index: Int32) throws {
        if let value {
            try bind(Int64(value), at: index)
        } else {
            try bindNull(at: index)
        }
    }

    func bind(_ value: Int64?, at index: Int32) throws {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        let result = value.map { sqlite3_bind_int64(handle, index, $0) }
            ?? sqlite3_bind_null(handle, index)
        try check(result)
    }

    func bind(_ value: Double?, at index: Int32) throws {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        let result = value.map { sqlite3_bind_double(handle, index, $0) }
            ?? sqlite3_bind_null(handle, index)
        try check(result)
    }

    func bind(_ value: Bool, at index: Int32) throws {
        try bind(Int64(value ? 1 : 0), at: index)
    }

    func bindNull(at index: Int32) throws {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        try check(sqlite3_bind_null(handle, index))
    }

    @discardableResult
    func step() throws -> Int32 {
        guard let handle else { throw OfflineStoreError.databaseClosed }
        let result = sqlite3_step(handle)
        guard result == SQLITE_ROW || result == SQLITE_DONE else {
            throw connection.error(statement: sql)
        }
        return result
    }

    func stepToCompletion() throws {
        guard try step() == SQLITE_DONE else {
            throw OfflineStoreError.sqlite(
                code: SQLITE_MISUSE,
                message: "Statement unexpectedly returned a row.",
                statement: sql
            )
        }
    }

    func isNull(_ column: Int32) -> Bool {
        guard let handle else { return true }
        return sqlite3_column_type(handle, column) == SQLITE_NULL
    }

    func string(_ column: Int32) -> String {
        guard let handle, let pointer = sqlite3_column_text(handle, column) else { return "" }
        return String(cString: pointer)
    }

    func optionalString(_ column: Int32) -> String? {
        isNull(column) ? nil : string(column)
    }

    func data(_ column: Int32) -> Data {
        guard let handle else { return Data() }
        let count = Int(sqlite3_column_bytes(handle, column))
        guard count > 0, let bytes = sqlite3_column_blob(handle, column) else {
            return Data()
        }
        return Data(bytes: bytes, count: count)
    }

    func int64(_ column: Int32) -> Int64 {
        guard let handle else { return 0 }
        return sqlite3_column_int64(handle, column)
    }

    func optionalInt64(_ column: Int32) -> Int64? {
        isNull(column) ? nil : int64(column)
    }

    func double(_ column: Int32) -> Double {
        guard let handle else { return 0 }
        return sqlite3_column_double(handle, column)
    }

    func optionalDouble(_ column: Int32) -> Double? {
        isNull(column) ? nil : double(column)
    }

    private func check(_ result: Int32) throws {
        guard result == SQLITE_OK else {
            throw connection.error(statement: sql)
        }
    }
}

private let sqliteTransient = unsafeBitCast(-1, to: sqlite3_destructor_type.self)
