# HikeJournalSync

`HikeJournalSync` is the transport-neutral, durable offline queue engine. It
depends on `HikeJournalPersistence` but deliberately does not own reachability,
`BGTaskScheduler`, `URLSession`, API routing, or UI.

The app constructs a `SyncCoordinator` with:

- `SyncOperationStore.offlineDatabase(accountDatabase)`
- a `SyncOperationExecutor` that maps each `PendingOperationKind` to the API and
  sends the supplied `SyncIdempotencyKey` with the request
- a connectivity provider, clock, and jitter source
- a cleanup callback that removes app-owned upload files
- an optional progress reporter

Call `drain(prioritizedPhotoID:)` immediately after enqueueing or when the app
returns online. A drain attempts each eligible row at most once, never sleeps,
and permits at most two eligible photo uploads at once. The returned
`SyncSchedulingHint` tells the app adapter whether to wait for connectivity,
authentication, user attention, or a bounded retry date. It does not pretend
that iOS background execution is guaranteed.

The coordinator delegates ordering to `SyncQueuePlanner`. After a hike-create
acknowledgement it durably releases waiting field marks. After a hike-delete
acknowledgement it durably removes blocked child mutations before removing the
delete intent, so a crash can only replay the idempotent deletion—not upload a
child into a deleted hike.

The executor returning is an explicit remote acknowledgement. The coordinator
then verifies durable queue deletion before invoking media cleanup. A crash in
either earlier window leaves the row replayable with the same idempotency key.
Executors classify transport failures by throwing `SyncExecutionFailure`.
