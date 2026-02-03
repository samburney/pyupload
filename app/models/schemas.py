"""Pydantic schemas generated from Tortoise ORM models.

IMPORTANT: This module MUST be imported AFTER Tortoise.init_models() has been called.
Import from `app.models` (not directly from this file) to ensure proper initialization.

The app.models.__init__ module calls Tortoise.init_models() at module load time,
which discovers model relationships. Only after that can pydantic_model_creator()
properly generate schemas that include relationship fields like 'user'.
"""
from tortoise.contrib.pydantic import pydantic_model_creator

from app.models.uploads import Upload


# Create Pydantic models - relationships are included because init_models() ran first
Upload_Pydantic = pydantic_model_creator(Upload, name="Upload")
