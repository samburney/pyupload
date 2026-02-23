from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `collections` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
        ALTER TABLE `collections` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);
        ALTER TABLE `tags` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6);
        ALTER TABLE `tags` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `collections` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL;
        ALTER TABLE `collections` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL;
        ALTER TABLE `tags` MODIFY COLUMN `created_at` DATETIME(6) NOT NULL;
        ALTER TABLE `tags` MODIFY COLUMN `updated_at` DATETIME(6) NOT NULL;"""


MODELS_STATE = (
    "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"
    "bzfR13ox5k2/nFr+D3zUv2E="
)
