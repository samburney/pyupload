from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `collections` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `name_unique` VARCHAR(255) NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `collection_upload` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `collection_id` INT NOT NULL,
    `upload_id` INT NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `images` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `upload_id` INT NOT NULL,
    `type` VARCHAR(255) NOT NULL,
    `width` INT NOT NULL,
    `height` INT NOT NULL,
    `bits` INT NOT NULL,
    `channels` INT NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `tags` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `name` VARCHAR(255) NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `tag_upload` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `tag_id` INT NOT NULL,
    `upload_id` INT NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `uploads` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `user_id` INT NOT NULL,
    `filegroup_id` INT NOT NULL DEFAULT 0,
    `description` VARCHAR(255) NOT NULL,
    `name` VARCHAR(255) NOT NULL,
    `cleanname` VARCHAR(255) NOT NULL,
    `originalname` VARCHAR(255) NOT NULL,
    `ext` VARCHAR(10) NOT NULL,
    `size` INT NOT NULL,
    `type` VARCHAR(255) NOT NULL,
    `extra` VARCHAR(32) NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL,
    `viewed` INT NOT NULL DEFAULT 0,
    `private` INT NOT NULL DEFAULT 0
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `users` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `username` VARCHAR(64) NOT NULL,
    `email` VARCHAR(255) NOT NULL,
    `password` VARCHAR(60) NOT NULL,
    `created_at` DATETIME(6) NOT NULL,
    `updated_at` DATETIME(6) NOT NULL,
    `remember_token` VARCHAR(100) NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS `aerich` (
    `id` INT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `version` VARCHAR(255) NOT NULL,
    `app` VARCHAR(100) NOT NULL,
    `content` JSON NOT NULL
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "eJztmttu2zgQQH/F8FMWyBaJ47rFvrnZFM1ikyxSd1u0KARaomUiFKlSVJy0yL+XpO7Xik"
    "HaShafbM9F4hxK5MzQ36YedSAOnp1SjKHNESXTvybfpgR4UHyp0R5OpsD3M50UcLDGytxO"
    "7ZQcrAPOgM2FagNwAIXIgYHNkB/fiIQYSyG1hSEibiYKCfoSQotTF/ItZELx6bMQI+LAOx"
    "gkP/0ba4MgdgpjRo68t5Jb/N5XsnPCXytDebe1JcYZeiQz9u/5lpLUGhEupS4kkAEO5eU5"
    "C+Xw5ejiYJOIopFmJtEQcz4O3IAQ81y4HRnYAqPgJ0YTqABdeZc/Z8fzF/OXJ4v5S2GiRp"
    "JKXjxE4WWxR46KwOVq+qD0gIPIQmHMuIUBZJYWvJzHjwkmvNoQJoKMYfbc9AliBk19Void"
    "bgGrR5bYl3iJIfaUlwfuLAyJy7cS0vPnLXT+X16fvlleHwirP2Q0VLz70bpwGatmka6K0I"
    "pD0iSZczNAU6A2gzJkC/Aqz7+FhiMP1jMtepaQOrHrs+RLPwG38FydX5y9XS0v/pMj94Lg"
    "C1ZIlqszqZkp6X1JerAooU8vMnl/vnozkT8nH68uzxQxGnCXqTtmdquPUzkmEHJqEbqzgJ"
    "MPOxEnosJMhr7zyJksepqZ/B0zKTOUzU1ur5WCNbBvdoA5VkVDZ7TJtqryZl5ZAghw1TxI"
    "mnKcleTtnY8pKCZLTTYd0zwrzMxNste7PKU52ctNoRbCit9YE7/owdfMl/M+YwLXk5Xw3A"
    "MqmMryFyla1zwkTUxVO7iFzrynj1zgVMAVZs31WGJvCrEU4Q454uLdn7vUfqzP3BYid1tT"
    "6zQSyxzGimyNeKABLDEfKy57CwiJ9/auKW/OZbTYTEtpwI0I01Lal5nsSSG1Au60poyS4s"
    "O2IooD15RQgyuhzBmXOZIZ9apr9s99mcn+7J/NZzGZ8kd7qTl9GeiOKudOi13mMNYK1PRx"
    "h3fe0rzGdVngotkz9cLgVjfzR8JHrG8bhKHLaOjrkSu7/Tp8R/1hlx9GBV1znVpyM+Wqqf"
    "ifsOLHEBBdjgUnAzOFSRlyEQFYl2fZzyBNkcK7mgZGM8nYfJgAj4868Ds+asQnVUV6Afpa"
    "8yA27tKJ+ViTG/Nfkqd4XxnQfGMjh2FCPJl1YHgya0QoVaYHvz+dW9OD38eZvEVwB3Xq3c"
    "xhlJWuz9CtiE4DWM5jNMT60v4MVL+x2vyU8sPW1qewMI3PQTY+dUvUvM8wM7XFvEOmtpg3"
    "ZmpSVcp1PYCwVq6bOAyT4E8pGHwQBDvKal7lZo55n2GiXHQp9RfNpf6iUuqbsmFfkk1TNu"
    "zLTDLoQW8NmchubqDWmU/Vc5jr3PFRt55mW1NTLXU9yZWXkCF7O63JlmNNa74MMhuTMA8o"
    "Yb4VZY7moW3OZZhv7k9J9uSroQExNh8mwCdb+gpZHiUckprE4J+3V5cN6V3mUgL5jogAPz"
    "nI5ocTjAL+uZ9YWyjKqAvJQALv4GL5ocz19N+rV+VdXl7g1e/eXh6+A4pJENE="
)
