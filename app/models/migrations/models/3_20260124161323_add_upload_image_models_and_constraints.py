from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `images` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);
        ALTER TABLE `images` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
        ALTER TABLE `uploads` DROP COLUMN `filegroup_id`;
        ALTER TABLE `uploads` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);
        ALTER TABLE `uploads` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
        ALTER TABLE `images` ADD CONSTRAINT `fk_images_uploads_e0196e18` FOREIGN KEY (`upload_id`) REFERENCES `uploads` (`id`) ON DELETE CASCADE;
        ALTER TABLE `uploads` ADD CONSTRAINT `fk_uploads_users_5a3e4278` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE RESTRICT;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `uploads` DROP FOREIGN KEY `fk_uploads_users_5a3e4278`;
        ALTER TABLE `images` DROP FOREIGN KEY `fk_images_uploads_e0196e18`;
        ALTER TABLE `images` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL;
        ALTER TABLE `images` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL;
        ALTER TABLE `uploads` ADD `filegroup_id` INT NOT NULL DEFAULT 0;
        ALTER TABLE `uploads` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL;
        ALTER TABLE `uploads` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL;"""


MODELS_STATE = (
    "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"
    "sf0fEbSiIA=="
)
