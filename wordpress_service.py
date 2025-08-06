import os
from dotenv import load_dotenv
import requests

from channel_service import ChannelService
from llm_service import LlmService

load_dotenv()


class WordpressService(ChannelService):
    def __init__(self):
        """Initialize WordpressService with WordPress API credentials."""
        self.base_url = os.getenv("WORDPRESS_API_URL")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('WORDPRESS_ACCESS_TOKEN')}",
        }
        self.llm_service = LlmService()

    def create(self, image_url: str, trend: str, affiliate_link: str = "") -> str:
        try:
            # Generate SEO-friendly title and content
            # TODO: use affiliate link to create title and content instead of trend to increase relevance
            title = self.get_post_title(trend)
            content = self.get_post_content(title, trend, affiliate_link)
            featured_media_id = self.upload_feature_image(image_url) if image_url else 0

            # Get or create tag IDs
            tag_names = [trend.lower(), "affiliate", "ad"]
            tag_ids = []
            for tag_name in tag_names:
                tag_id = self.get_or_create_tag(tag_name)
                if tag_id:
                    tag_ids.append(tag_id)

            # Create the post
            url = f"{self.base_url}/posts"
            payload = {
                "title": title,
                "content": content,
                "status": "publish",
                "featured_media": featured_media_id,
                "categories": [],
                "tags": tag_ids,  # Use tag IDs
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            post_data = response.json()
            post_url = post_data.get("link", "")
            return post_url
        except (requests.RequestException, ValueError) as e:
            print(
                f"Error creating post: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return ""

    def upload_feature_image(self, image_url: str) -> int:
        """
        Uploads an image to WordPress media library and returns the media ID.
        """
        try:
            # Download the image
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            image_data = image_response.content

            # Upload to WordPress
            url = f"{self.base_url}/media"
            headers = self.headers.copy()
            headers.pop("Content-Type", None)  # Remove for multipart upload
            files = {"file": ("image.jpg", image_data, "image/jpeg")}
            response = requests.post(
                url, headers=headers, files=files, data={"title": "Featured Image"}
            )
            response.raise_for_status()
            return response.json().get("id", 0)
        except requests.RequestException as e:
            print(
                f"Error uploading image: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return 0

    def get_or_create_tag(self, tag_name: str) -> int:
        """Get or create a tag and return its ID."""
        try:
            # Check if tag exists
            response = requests.get(
                f"{self.base_url}/tags",
                headers=self.headers,
                params={"search": tag_name},
            )
            response.raise_for_status()
            tags = response.json()
            for tag in tags:
                if tag["name"].lower() == tag_name.lower():
                    return tag["id"]
            # Create tag if not found
            response = requests.post(
                f"{self.base_url}/tags", headers=self.headers, json={"name": tag_name}
            )
            response.raise_for_status()
            return response.json().get("id", 0)
        except requests.RequestException as e:
            print(
                f"Error getting/creating tag {tag_name}: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return 0

    def get_post_title(self, trend: str) -> str:
        try:
            prompt = f"Create a WordPress blog post title about '{trend}' ideas that is SEO-friendly and time-agnostic, respond with the title only."
            return self.llm_service.generate_text(prompt)
        except Exception as e:
            print(f"Error generating title: {e}")
            return f"Top {trend} Trends to Explore #ad"

    def get_post_content(self, title: str, trend: str, affiliate_link: str) -> str:
        """
        Generates SEO-friendly post content with affiliate link.
        """
        try:
            prompt = f"Create a WordPress blog post body for the title '{title}' that is SEO-friendly and time-agnostic. Respond with the content only (500-700 words)."
            content = self.llm_service.generate_text(prompt)

            if affiliate_link:
                content += f"\n\n<a href='{affiliate_link}' target='_blank'>Shop {trend} Now #ad</a>\n\nDisclosure: This post contains affiliate links."
            return content
        except Exception as e:
            print(f"Error generating content: {e}")
            return f"Explore the latest {trend} trends with our curated selection! Check out top products to inspire your next purchase. <a href='{affiliate_link}' target='_blank'>Shop Now #ad</a>\n\nDisclosure: This post contains affiliate links."


if __name__ == "__main__":
    service = WordpressService()
    service.create(
        image_url="https://images.pexels.com/photos/20638732/pexels-photo-20638732.jpeg",
        trend="Anime",
        affiliate_link="https://example.com/affiliate-link",
    )
