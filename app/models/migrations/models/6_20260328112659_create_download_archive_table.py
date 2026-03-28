from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `download_archives` (
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `id` CHAR(36) NOT NULL PRIMARY KEY,
    `upload_ids` JSON NOT NULL,
    `filename` VARCHAR(255) NOT NULL,
    `format` VARCHAR(8) NOT NULL COMMENT 'zip: zip\ntar_gzip: tar.gz\ntar_bzip: tar.bz2\ntar_xz: tar.xz\ntar_zstd: tar.zstd' DEFAULT 'zip',
    `status` VARCHAR(10) NOT NULL COMMENT 'pending: pending\nprocessing: processing\nready: ready\nfailed: failed' DEFAULT 'pending',
    `user_id` INT NOT NULL,
    CONSTRAINT `fk_download_users_7d5b7cca` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) CHARACTER SET utf8mb4;
        ALTER TABLE `collections` ADD CONSTRAINT `fk_collecti_users_5600ea46` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE `collections` DROP FOREIGN KEY `fk_collecti_users_5600ea46`;
        DROP TABLE IF EXISTS `download_archives`;"""


MODELS_STATE = (
    "eJztXW1P2zoU/itRP+1KvQhKxxC6ulJ5mcY24IqVu6uNKXIbN7VIncxxKGXiv1/beU+ckJ"
    "SGNa2/QHvsk9jP8ct5fHLSX52ZbUDL3TmxLQuOKbJx50j71cFgBtkHSWlX6wDHicu4gIKR"
    "JaqPo3pCDkYuJWBMWdEEWC5kIgO6Y4Kc4EbYsywutMesIsJmLPIw+ulBndompFNIWMH3H0"
    "yMsAEfoBt+de70CYKWkWozMvi9hVynC0fIzjF9Lyryu4101k5vhuPKzoJObRzVRphyqQkx"
    "JIBCfnlKPN583rqgs2GP/JbGVfwmJnQMOAGeRRPdrYjBmMHI8GOtcUUHTX6XP3t7/Xf9w/"
    "2D/iGrIloSSd49+d2L++4rCgQuh50nUQ4o8GsIGGPcxgTyzuqA5vE7ZSUUzaAcxLRmBkwj"
    "UN0JP2ShDYEswzYUxODGA2pF6LI+GFfYWgSGK4FyeH5x9mU4uPiH92Tmuj8tAdFgeMZLek"
    "K6yEjfHPzB5TabDv5UiS6ifT0fftD4V+3b1eWZQNB2qUnEHeN6w28d3ibgUVvH9lwHRmKM"
    "hdIQGFYzNqznGEsaNq2pDPtbDRs0Prar+J+z6MkUELk1w/oZOzKw1tRyM/CgWxCbdMpXub"
    "dvS0z37+D65MPg+g2rlbHHZVDU88uechDqQZdqIplQU4DGa40LiV5rB05oPL8NrwmOK9iJ"
    "ufsyuZNuxByRPIDvbQKRiT/BhcDxnLUI4LFs/AVO201wmfXD7ykcA6E0Xu8ImEcuXXJosO"
    "6xTkHqT8zBl5PB6VlHgDgC47s5IIaeQpOX2D07I4nq5otmvZncGI5lA8PN2+MC4MXQ5n+r"
    "2kNcaRmLNO1ZlthDtF3P0IG4JwRawkGIfMg0AZjYRMB9Bxfp0sCqkT2CCj7YQSGdEtszpx"
    "lFL7q3dEgwuZ7128UwmQEMTCHiGDx1Jdwm6FYp/4m7XoUFJVqruNC6rcDdMi6UHakVIczp"
    "bdOWluYciZlc1RNI6mwTcDlfoLF9rXQlPLXnmFtgQMZTdA9lC2G2Suk6aASVdeDXXrMzoZ"
    "ub89MaC6HnIWOH6zSzg3f+mnhYrByauBP/0/+78+JNXTbqhGO/7xPXJCUVvVOHRFtwlqAO"
    "iTbUsLlDomhTlVCYj1+uLp/Zil2JTW8wQ/e7gca0q1nIpT/W06YlNuQdT5kvPNN4czH4L3"
    "vccfL56jhrF36B44zLM0EWrHskl9RRp0gxlDaZyRYiDuQZ9mY5xp0GNdJ+PUg7j8jJb9Zc"
    "eqSxP7eYAqKb4iv7tGM++pJRJBk99nzRw6MveAiqPLrU8CX8U2cJEx1WMNBhoXkOs8ZhqF"
    "NPsppUM06s/YrGcSA2OF55AwUlR1rw4RY7xB5D1/WF0edbzHeIxZEm/t3iCWAz1+A34/+X"
    "screbgWz7O0W2oUXqbNXdfa6cWevpRz1fAZMKTP1C7plfBTxKmtGQtVhnHowYUuoieKcG2"
    "rYHOcUhpD6h3JrhvUVA4ognCODXbz6dhHV3yY/LgnYlDloU8k6UohYrLCtkI0QldC4QsDC"
    "6tsK13gKMA58yqrhwITKtsKmIoErYqbRowQv5aZLP4eyRuw0OUDWiZ9ewwlzo6ZD+w5Kn6"
    "RPlXfL2CrxazKmyapWY62dC34ZbWITzaU2B1r7+HWoBVfS/Ctpc0SnTHZvj4EIN7qe49iE"
    "7mQPsV5+NcWVFVdWlEpxZWXYEq7Ml1F9ClwJ2ythzCmtpnjzqte+FG0+6FdgzQf9QtLMi9"
    "KeJnxwELPLElMkrdnOKdKSKRF2u3Sx4/7EHZS4AMe2bUGA5VZMaGVMOGJqTVmtbgChutmO"
    "r64+pyx2fD7MzIabi+Oz6zd7wlSsEvJ9YAkJU6FBFRrc8NDgEJgdCePi4m4Z0aLAVEFBRX"
    "RatdlvjD+siM6GGlZlK68mKPh6uSEq53G5nMfQf8gkOzJxzSxHrrHy9Ebm/hTnNcaFz3lI"
    "KpOxpX5SPAwrYhcrbBPvUxHLducuClYtWeFCtl28uHE2q/hf69Y1xf82giYo/rehhs0nIr"
    "J1ti4HTOq0kwc2EOWaAWTVATFSaCeCjTxe6wDXndtEsvcW45jUaSeUB1VSzg6KU84Ociln"
    "yNUJNJFLIakdrsvpqqBdDlwwAtiw8TLYplQVtHlojRnCS8AaqilIc5AayOXdXGKwJjUVsN"
    "n3CmATEoe1hNZ+Tkimu9TeFTh4m/OwUBIZTjLzqBa/HUOmu4J3ZDyP8Ss+M9TIKzL8/Z4A"
    "/wVpTp2RLFFtaCA364P1q3iz/WJntp/zZS3gUt2yTVQX0pyiAjQG1IUQL3EGkdVdwSnEWi"
    "0L63ToUPgoYY0zadkrHyWBz+NA+f2nax79C34IQR7zTP9YwvpxwqLIZ2oOSN/dtzwmkvcG"
    "thSYfFrO8qhkk4FaCknh4wJ1sGhjVtpToxGtwqh9lZB9wiaNxrW+d5gbfM+sxe+UiKz8UA"
    "Gvrgp4qbiICnhti2HzLlQCkJxhi1lZRq2dkYbGfqylDpLtjhw2AuGYn8LWxTGlpMCMwLQJ"
    "MhEGVl08s3oK0kQKZ8FbXwtC2w+v/JrXVQK4+heAuuhRMhALneuw+jY9rqheU7bq+UokoZ"
    "PSGUtk8ZKWgLjfq4Dhfq8QQl6URvAewbksYlo4a2OF15u3u+szaRPHDRUBS2hsJWIq91vl"
    "fjee+33NyPL1+cmwLPk7cQYYvYl5+QPj6IXP7QHzpefFqayeVaTnBbnxbc/NC7qRTcxLxi"
    "XSuXmpbJ1sel6cAPWy3Lz8SV9piLG28V4WZ1w3G6Z7syJT5n6ObyW/KRkHmQuDNwNI0Hja"
    "kQRvgpJuWfAGxHVUTtKaOQndkhDNPSRuzdPehEo7GVEjtJJPjRogBtXbCeDebrVzoLKDoN"
    "xJELsjhVhyllb8UGNCRf3eVzYaFD7M+FuzXZ/+B6TNAD8="
)
