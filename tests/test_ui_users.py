
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token

class TestUserProfileEndpoint:
    """Test GET /profile endpoint."""

    @pytest.mark.asyncio
    async def test_profile_page_default_sorting(self, client, monkeypatch):
        """Test that profile page uses created_at desc sorting by default."""
        
        # Create and authenticate a user
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.is_registered = True
        mock_user.max_uploads_count = -1  # Unlimited
        mock_user.uploads_count = AsyncMock(return_value=0)
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        token = create_access_token({"sub": "testuser"})
        client.cookies = {"access_token": token}
        
        # Mock Upload.paginate and Upload.pages to avoid DB queries and check arguments
        with patch("app.models.uploads.Upload.paginate") as mock_paginate, \
             patch("app.models.uploads.Upload.pages", new_callable=AsyncMock) as mock_pages:
            
            # Set up the mock chain for paginate
            # await Upload.paginate(...).all().prefetch_related("images")
            mock_qs_after_paginate = MagicMock()
            mock_qs_after_all = MagicMock()
            
            # Create a real coroutine to return
            async def get_results():
                return []
                
            mock_paginate.return_value = mock_qs_after_paginate
            mock_qs_after_paginate.all.return_value = mock_qs_after_all
            mock_qs_after_all.prefetch_related.return_value = get_results()
            
            mock_pages.return_value = 1
            
            # Make request
            response = await client.get("/profile")
            
            assert response.status_code == 200
            
            # Verify default sorting was applied
            call_kwargs = mock_paginate.call_args[1]
            assert call_kwargs.get("sort_by") == "created_at"
            assert call_kwargs.get("sort_order") == "desc"

    @pytest.mark.asyncio
    async def test_profile_page_explicit_sorting(self, client, monkeypatch):
        """Test that profile page respects explicit sorting parameters."""
        
        # Create and authenticate a user
        mock_user = MagicMock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.is_registered = True
        mock_user.max_uploads_count = -1  # Unlimited
        mock_user.uploads_count = AsyncMock(return_value=0)
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        token = create_access_token({"sub": "testuser"})
        client.cookies = {"access_token": token}
        
        with patch("app.models.uploads.Upload.paginate") as mock_paginate, \
             patch("app.models.uploads.Upload.pages", new_callable=AsyncMock) as mock_pages:
            
            mock_qs_after_paginate = MagicMock()
            mock_qs_after_all = MagicMock()
            
            async def get_results():
                return []
            
            mock_paginate.return_value = mock_qs_after_paginate
            mock_qs_after_paginate.all.return_value = mock_qs_after_all
            mock_qs_after_all.prefetch_related.return_value = get_results()
            
            mock_pages.return_value = 1
            
            # Make request with explicit sorting
            response = await client.get("/profile?sort_by=size&sort_order=asc")
            
            assert response.status_code == 200
            
            # Verify explicit sorting was applied
            call_kwargs = mock_paginate.call_args[1]
            assert call_kwargs.get("sort_by") == "size"
            assert call_kwargs.get("sort_order") == "asc"


class TestUserProfileIntegration:
    """Integration tests for user profile page rendering."""

    @pytest.mark.asyncio
    async def test_profile_empty_state(self, client):
        """Test profile page with no uploads."""
        # Create user but no uploads
        user = await User.create(username="testuser", email="test@example.com", is_registered=True, password="password")
        
        # Authenticate
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        
        response = await client.get("/profile")
        assert response.status_code == 200
        html = response.text
        
        assert "Profile" in html
        assert user.username in html
        # Should not show Files section
        assert "Files" not in html
        assert "Filename:" not in html

    @pytest.mark.asyncio
    async def test_profile_renders_uploads(self, client):
        """Test rendering of mixed upload types (image vs file)."""
        user = await User.create(username="gallery_user", email="gallery@example.com", is_registered=True, password="password")
        
        # Authenticate
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        
        # Create non-image upload
        text_upload = await Upload.create(
            user=user,
            description="A text file",
            name="notes",
            cleanname="notes",
            originalname="notes.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra=""
        )
        
        # Create image upload
        image_upload = await Upload.create(
            user=user,
            description="An image",
            name="photo",
            cleanname="photo",
            originalname="photo.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra=""
        )
        # Create associated Image record
        from app.models.images import Image
        await Image.create(
            upload=image_upload,
            type="jpeg",
            width=100,
            height=100, 
            bits=8, 
            channels=3
        )
        
        response = await client.get("/profile")
        assert response.status_code == 200
        html = response.text
        
        # Check text upload rendering
        assert "notes.txt" in html
        assert "text/plain" in html
        # Should have generic placeholder (div with ext)
        assert ".txt" in html
        
        # Check image upload rendering
        assert "photo.jpg" in html
        assert "image/jpeg" in html
        # Should have img tag
        assert "<img" in html
        assert f'src="{image_upload.url}"' in html

    @pytest.mark.asyncio
    async def test_profile_pagination_integration(self, client):
        """Test that profile lists uploads and respects existing pagination logic."""
        user = await User.create(username="paged_user", email="paged@example.com", is_registered=True, password="password")
        
        # Authenticate
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        
        # Create 15 uploads
        for i in range(15):
             await Upload.create(
                user=user,
                description=f"File {i}",
                name=f"file{i}",
                cleanname=f"file{i}",
                originalname=f"file{i}.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra=""
            )
            
        response = await client.get("/profile")
        assert response.status_code == 200
        html = response.text
        
        # Should show some files
        assert "file14.txt" in html # Depending on sort order (desc created_at), 14 should be first
        
        # We don't strictly assert exactly 10 items here effectively without parsing,
        # but we verified the paginate call args in the unit test.
        # Just ensure the page renders without error with multiple items.
        assert html.count("Filename:") <= 10 # Default page size is 10

