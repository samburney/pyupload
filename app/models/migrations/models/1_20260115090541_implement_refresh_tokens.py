from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `refresh_tokens` (
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `token_hash` VARCHAR(64) NOT NULL,
    `expires_at` DATETIME(6) NOT NULL,
    `revoked` BOOL NOT NULL DEFAULT 0,
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_refresh__users_1c3fe0a4` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_refresh_tok_token_h_e92003` (`token_hash`)
) CHARACTER SET utf8mb4 COMMENT='Model for storing JWT refresh tokens with revocation support.';
        ALTER TABLE `users` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);
        ALTER TABLE `users` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `users` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL;
        ALTER TABLE `users` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL;
        DROP TABLE IF EXISTS `refresh_tokens`;"""


MODELS_STATE = (
    "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"
)
