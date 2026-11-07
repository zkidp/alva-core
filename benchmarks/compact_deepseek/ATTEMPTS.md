# Preparation and post-run disclosure

All preparation here preceded formal generation at the freeze commit.

1. The user-linked credential file was initially empty on disk. The user saved
   it after clarification; metadata authentication and account availability then
   succeeded. These were metadata requests, not model generation.
2. The first local transport preparation produced a task-owned SSH key with an
   unintended passphrase due to shell argument handling. The server accepted the
   public key but noninteractive signing failed. `preflight01` stopped before
   an owned candidate service or a model request was launched. The key was
   corrected before the successful preflight. No existing account key was changed.
   This fault is documented from tool output; a standalone original stderr log
   was not retained and is not claimed to exist in the archive.
3. `preflight02` ran all four tasks in both real isolated routes, retaining
   baseline failures, deterministic passing witnesses, actual Native publication,
   fresh authority and owner cleanup receipts. Generation calls = 0.
4. The single formal wave used exactly sixteen scheduled fresh conversations.
   There were no common infrastructure faults, replacement slots, operator
   repairs or subsequent model waves. Three token-observation failures remain
   failures. A discarded Native staged proposal was not rescued after the run.
5. Post-run request reconstruction and evidence checking pass all sixteen rows.
   The original frozen runner and primary analysis are unchanged. Additional
   diagnosis, validation and consumed-freeze protection are labelled post-run.

The preparation archive contains successful preflight receipts and post-run SDK/
transport cleanup confirmations. It excludes credentials, connection files and
account-balance data. The original historical experiments are not rewritten.
