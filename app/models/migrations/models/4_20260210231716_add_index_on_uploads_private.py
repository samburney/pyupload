from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `uploads` ADD INDEX `idx_uploads_private_1d7466` (`private`, `created_at`);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `uploads` DROP INDEX `idx_uploads_private_1d7466`;"""


MODELS_STATE = (
    "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"
    "MhGVPdTFvN5GX2lhzKt+acXmfzX/qrM="
)
