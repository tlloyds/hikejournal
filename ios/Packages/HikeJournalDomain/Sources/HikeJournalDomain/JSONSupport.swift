import Foundation

/// The shared API uses snake_case. Keeping construction here prevents a caller
/// from silently decoding the same model with incompatible key semantics.
public enum HikeJournalDomainJSON {
    public static func decoder() -> JSONDecoder {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }

    public static func encoder() -> JSONEncoder {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        encoder.outputFormatting = [.sortedKeys]
        return encoder
    }

    public static func decode<Value: Decodable>(
        _ type: Value.Type = Value.self,
        from data: Data
    ) throws -> Value {
        try decoder().decode(type, from: data)
    }

    public static func decode<Value: Decodable>(
        _ type: Value.Type = Value.self,
        from json: String
    ) throws -> Value {
        try decode(type, from: Data(json.utf8))
    }

    public static func encode<Value: Encodable>(_ value: Value) throws -> Data {
        try encoder().encode(value)
    }
}

struct DomainKey: CodingKey, Hashable {
    let stringValue: String
    let intValue: Int?

    init(_ stringValue: String) {
        self.stringValue = stringValue
        intValue = nil
    }

    init?(stringValue: String) {
        self.init(stringValue)
    }

    init?(intValue: Int) {
        stringValue = String(intValue)
        self.intValue = intValue
    }
}

extension Decoder {
    func domainContainer() throws -> KeyedDecodingContainer<DomainKey> {
        try container(keyedBy: DomainKey.self)
    }
}

extension KeyedDecodingContainer where Key == DomainKey {
    private func resolvedKey(_ name: String) -> DomainKey {
        let exact = DomainKey(name)
        guard !contains(exact) else { return exact }
        let snakeCase = DomainKey(name.domainSnakeCased)
        return contains(snakeCase) ? snakeCase : exact
    }

    func string(_ name: String, default defaultValue: String = "") -> String {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return defaultValue }
        if let value = try? decode(String.self, forKey: key) { return value }
        if let value = try? decode(Int64.self, forKey: key) { return String(value) }
        if let value = try? decode(Double.self, forKey: key), value.isFinite {
            return String(value)
        }
        if let value = try? decode(Bool.self, forKey: key) { return String(value) }
        return defaultValue
    }

    func optionalString(_ name: String) -> String? {
        let value = string(name).trimmingCharacters(in: .whitespacesAndNewlines)
        return value.isEmpty ? nil : value
    }

    func integer(_ name: String, default defaultValue: Int = 0) -> Int {
        optionalInteger(name) ?? defaultValue
    }

    func optionalInteger(_ name: String) -> Int? {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return nil }
        if let value = try? decode(Int.self, forKey: key) { return value }
        if let value = try? decode(Int64.self, forKey: key), let converted = Int(exactly: value) {
            return converted
        }
        if let value = try? decode(Double.self, forKey: key), value.isFinite,
           value >= Double(Int.min), value <= Double(Int.max) {
            return Int(value)
        }
        if let value = try? decode(String.self, forKey: key) {
            return Int(value.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return nil
    }

    func int64(_ name: String, default defaultValue: Int64 = 0) -> Int64 {
        optionalInt64(name) ?? defaultValue
    }

    func optionalInt64(_ name: String) -> Int64? {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return nil }
        if let value = try? decode(Int64.self, forKey: key) { return value }
        if let value = try? decode(Int.self, forKey: key) { return Int64(value) }
        if let value = try? decode(Double.self, forKey: key), value.isFinite,
           value >= Double(Int64.min), value <= Double(Int64.max) {
            return Int64(value)
        }
        if let value = try? decode(String.self, forKey: key) {
            return Int64(value.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return nil
    }

    func double(_ name: String, default defaultValue: Double = 0) -> Double {
        optionalDouble(name) ?? defaultValue
    }

    func optionalDouble(_ name: String) -> Double? {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return nil }
        let decoded: Double?
        if let value = try? decode(Double.self, forKey: key) {
            decoded = value
        } else if let value = try? decode(Int64.self, forKey: key) {
            decoded = Double(value)
        } else if let value = try? decode(String.self, forKey: key) {
            decoded = Double(value.trimmingCharacters(in: .whitespacesAndNewlines))
        } else {
            decoded = nil
        }
        return decoded.flatMap { $0.isFinite ? $0 : nil }
    }

    func boolean(_ name: String, default defaultValue: Bool = false) -> Bool {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return defaultValue }
        if let value = try? decode(Bool.self, forKey: key) { return value }
        if let value = try? decode(Int.self, forKey: key) { return value != 0 }
        if let value = try? decode(String.self, forKey: key) {
            switch value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
            case "true", "1", "yes": return true
            case "false", "0", "no": return false
            default: return defaultValue
            }
        }
        return defaultValue
    }

    func optionalBoolean(_ name: String) -> Bool? {
        let key = resolvedKey(name)
        guard contains(key), (try? decodeNil(forKey: key)) != true else { return nil }
        if let value = try? decode(Bool.self, forKey: key) { return value }
        if let value = try? decode(Int.self, forKey: key) { return value != 0 }
        if let value = try? decode(String.self, forKey: key) {
            switch value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() {
            case "true", "1", "yes": return true
            case "false", "0", "no": return false
            default: return nil
            }
        }
        return nil
    }

    func value<Value: Decodable>(
        _ type: Value.Type = Value.self,
        _ name: String
    ) throws -> Value {
        try decode(type, forKey: resolvedKey(name))
    }

    func optionalValue<Value: Decodable>(
        _ type: Value.Type = Value.self,
        _ name: String
    ) throws -> Value? {
        try decodeIfPresent(type, forKey: resolvedKey(name))
    }

    func array<Value: Decodable>(
        _ type: Value.Type = Value.self,
        _ name: String
    ) throws -> [Value] {
        try decodeIfPresent([Value].self, forKey: resolvedKey(name)) ?? []
    }

    func dictionary<Value: Decodable>(
        _ type: Value.Type = Value.self,
        _ name: String
    ) throws -> [String: Value] {
        try decodeIfPresent([String: Value].self, forKey: resolvedKey(name)) ?? [:]
    }
}

func encodeDomain<Value: Encodable>(
    _ value: Value,
    to encoder: Encoder,
    key: String
) throws {
    var container = encoder.container(keyedBy: DomainKey.self)
    try container.encode(value, forKey: DomainKey(key))
}

extension String {
    fileprivate var domainSnakeCased: String {
        var output = ""
        let characters = Array(self)
        for (index, character) in characters.enumerated() {
            if character.isUppercase {
                let previous = index > 0 ? characters[index - 1] : nil
                let next = index + 1 < characters.count ? characters[index + 1] : nil
                if index > 0,
                   previous?.isLowercase == true ||
                    (previous?.isUppercase == true && next?.isLowercase == true) {
                    output.append("_")
                }
                output.append(contentsOf: character.lowercased())
            } else {
                output.append(character)
            }
        }
        return output
    }

    var domainTrimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }

    var domainFolded: String {
        domainTrimmed.folding(
            options: [.caseInsensitive, .diacriticInsensitive],
            locale: Locale(identifier: "en_US_POSIX")
        )
    }
}

func validLatitude(_ value: Double?) -> Double? {
    value.flatMap { $0.isFinite && (-90.0...90.0).contains($0) ? $0 : nil }
}

func validLongitude(_ value: Double?) -> Double? {
    value.flatMap { $0.isFinite && (-180.0...180.0).contains($0) ? $0 : nil }
}
