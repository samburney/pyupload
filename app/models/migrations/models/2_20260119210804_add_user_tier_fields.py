from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` ADD `is_abandoned` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `last_login_ip` VARCHAR(45);
        ALTER TABLE `users` ADD `is_registered` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `last_seen_at` DATETIME(6);
        ALTER TABLE `users` ADD `is_admin` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `fingerprint_data` JSON;
        ALTER TABLE `users` ADD `registration_ip` VARCHAR(45);
        ALTER TABLE `users` ADD `fingerprint_hash` VARCHAR(64);
        ALTER TABLE `users` ADD `is_disabled` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD INDEX `idx_users_fingerp_62b4da` (`fingerprint_hash`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP INDEX `idx_users_fingerp_62b4da`;
        ALTER TABLE `users` DROP COLUMN `is_abandoned`;
        ALTER TABLE `users` DROP COLUMN `last_login_ip`;
        ALTER TABLE `users` DROP COLUMN `is_registered`;
        ALTER TABLE `users` DROP COLUMN `last_seen_at`;
        ALTER TABLE `users` DROP COLUMN `is_admin`;
        ALTER TABLE `users` DROP COLUMN `fingerprint_data`;
        ALTER TABLE `users` DROP COLUMN `registration_ip`;
        ALTER TABLE `users` DROP COLUMN `fingerprint_hash`;
        ALTER TABLE `users` DROP COLUMN `is_disabled`;"""


MODELS_STATE = (
    "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"
    "Cw3/k="
)
