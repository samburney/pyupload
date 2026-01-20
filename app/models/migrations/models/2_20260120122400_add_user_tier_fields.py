from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` ADD `fingerprint_hash` VARCHAR(64);
        ALTER TABLE `users` ADD `is_abandoned` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `fingerprint_data` JSON;
        ALTER TABLE `users` ADD `is_disabled` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `registration_ip` VARCHAR(45);
        ALTER TABLE `users` ADD `last_login_ip` VARCHAR(45);
        ALTER TABLE `users` ADD `is_registered` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` ADD `last_seen_at` DATETIME(6);
        ALTER TABLE `users` ADD `is_admin` BOOL NOT NULL DEFAULT 0;
        ALTER TABLE `users` DROP COLUMN `remember_token`;
        ALTER TABLE `users` ADD INDEX `idx_users_fingerp_62b4da` (`fingerprint_hash`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` DROP INDEX `idx_users_fingerp_62b4da`;
        ALTER TABLE `users` ADD `remember_token` VARCHAR(100) NOT NULL;
        ALTER TABLE `users` DROP COLUMN `fingerprint_hash`;
        ALTER TABLE `users` DROP COLUMN `is_abandoned`;
        ALTER TABLE `users` DROP COLUMN `fingerprint_data`;
        ALTER TABLE `users` DROP COLUMN `is_disabled`;
        ALTER TABLE `users` DROP COLUMN `registration_ip`;
        ALTER TABLE `users` DROP COLUMN `last_login_ip`;
        ALTER TABLE `users` DROP COLUMN `is_registered`;
        ALTER TABLE `users` DROP COLUMN `last_seen_at`;
        ALTER TABLE `users` DROP COLUMN `is_admin`;"""


MODELS_STATE = (
    "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"
)
