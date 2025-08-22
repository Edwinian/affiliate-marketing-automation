import os
from dotenv import load_dotenv
import requests
from typing import List, Dict
import base64

from all_types import WordpressPost, WordpressCategory
from channel_service import ChannelService
from llm_service import LlmService

load_dotenv()


class WordpressService(ChannelService):
    POSTS: List[WordpressPost] = []

    def __init__(self):
        """Initialize WordpressService with WordPress API credentials."""
        self.api_url = os.getenv("WORDPRESS_API_URL")
        self.frontend_url = os.getenv("WORDPRESS_FRONTEND_URL")
        username = os.getenv("WORDPRESS_USERNAME")
        app_password = os.getenv("WORDPRESS_APP_PASSWORD")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64.b64encode(f'{username}:{app_password}'.encode()).decode()}",
        }
        self.llm_service = LlmService()

    def get_posts(self) -> List[WordpressPost]:
        """
        Retrieve all blog posts from WordPress, including category information.
        Returns a list of WordpressPost objects.
        """
        if self.POSTS:
            return self.POSTS

        try:
            posts = []
            page = 1
            per_page = 100

            while True:
                print(f"Fetching page {page} of {per_page} posts...")
                url = f"{self.api_url}/posts"
                params = {
                    "page": page,
                    "per_page": per_page,
                    "_embed": "wp:term",
                }
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                page_posts = response.json()

                if not page_posts:
                    break

                for post in page_posts:
                    categories = []
                    if "_embedded" in post and "wp:term" in post["_embedded"]:
                        for term_group in post["_embedded"]["wp:term"]:
                            for term in term_group:
                                if term.get("taxonomy") == "category":
                                    categories.append(
                                        WordpressCategory(
                                            id=term.get("id", 0),
                                            name=term.get("name", ""),
                                            slug=term.get("slug", ""),
                                        )
                                    )

                    post_data = WordpressPost(
                        id=post.get("id", 0),
                        title=post.get("title", {}).get("rendered", ""),
                        content=post.get("content", {}).get("rendered", ""),
                        link=post.get("link", ""),
                        date=post.get("date", ""),
                        status=post.get("status", ""),
                        categories=categories,
                    )
                    posts.append(post_data)

                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1

            self.POSTS = posts
            return posts

        except requests.RequestException as e:
            print(
                f"Error retrieving posts: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return []
        except ValueError as e:
            print(f"Error parsing response: {e}")
            return []

    def get_post_categories(self) -> Dict[str, WordpressCategory]:
        """
        Retrieve unique categories from existing blog posts.
        Returns a dictionary mapping category slugs to WordpressCategory objects.
        """
        try:
            posts = self.get_posts()
            categories = {}

            for post in posts:
                for category in post.categories:
                    if category.slug not in categories:
                        categories[category.slug] = category

            return categories

        except Exception as e:
            print(f"Error retrieving categories: {e}")
            return {}

    def get_navbar_html(self) -> str:
        """
        Create a navigation bar with a tab for each unique category from existing blog posts.
        Returns an HTML string representing the navbar, with each tab linking to the category archive page.

        Usage: Manually Add Navbar HTML to Theme Files

        To integrate the generated navbar HTML into your self-hosted WordPress site, follow these steps:
        1. **Generate the Navbar HTML**:
           - Run this method (e.g., via a local Python script or AWS Lambda) to obtain the HTML string.
           - Example command: `python script.py`
           - Example output: `<nav class="dynamic-nav"><ul><li><a href="https://example.com/category/anime">Anime</a></li><li><a href="https://example.com/category/trends">Trends</a></li></ul></nav>`
           - Copy the HTML string from the console or log output.

        2. **Access Theme Files**:
           - Log in to your WordPress admin panel (e.g., https://example.com/wp-admin).
           - Navigate to **Appearance > Theme File Editor** to edit your active theme's files.
           - Alternatively, use an FTP client (e.g., FileZilla) to access the theme directory at `/wp-content/themes/your-theme/`.
           - Recommended: Create a child theme to preserve changes during theme updates. In the child theme, copy `header.php` from the parent theme and modify it.

        3. **Edit the Theme File**:
           - Open `header.php` in the Theme File Editor or via FTP.
           - Locate the existing navigation menu or the section where the navbar should appear (e.g., within `<header>` or `<nav>` tags).
           - Replace or add the copied navbar HTML. Example:
             ```php
             <header>
                 <!-- Dynamic Navbar -->
                 <nav class="dynamic-nav">
                     <ul>
                         <li><a href="https://example.com/category/anime">Anime</a></li>
                         <li><a href="https://example.com/category/trends">Trends</a></li>
                     </ul>
                 </nav>
             </header>
             ```
           - If your theme uses a navigation menu (e.g., `wp_nav_menu`), you can replace it with the static HTML or keep both, depending on your design.
           - Save the changes in the Theme File Editor or upload the modified `header.php` via FTP.

        4. **Verify the Navbar**:
           - Visit your site (e.g., https://example.com) to ensure the navbar appears correctly.
           - Click each category link (e.g., https://example.com/category/anime) to confirm it loads the correct category archive page.
           - If the navbar doesn’t display as expected, check for theme-specific wrappers or conflicting CSS.

        5. **Update Process**:
           - When new categories are added or removed, rerun this method to generate updated HTML.
           - Copy the new HTML and manually update `header.php` in the Theme File Editor or via FTP.
           - To streamline updates, consider saving the HTML to a local file (e.g., `navbar.html`) and copy-paste it into `header.php` as needed.
           - Frequency: This manual process is suitable if categories change infrequently. For frequent changes, consider a programmatic approach (not recommended here due to performance concerns).

        6. **Notes**:
           - **Child Theme**: Using a child theme prevents loss of changes during parent theme updates. Create one via **Appearance > Theme File Editor** or FTP by following WordPress child theme documentation.
           - **Permalinks**: The `link` field in `WordpressCategory` ensures correct category URLs (e.g., `https://example.com/category/anime`), even with custom permalinks set in **Settings > Permalinks**.
           - **Backup**: Before editing theme files, back up `header.php` and the theme directory to avoid accidental data loss.
           - **Alternative Files**: If your theme uses a different template for the header (e.g., `template-parts/header.php`), locate it in the Theme File Editor or FTP and add the HTML there.
           - **Performance**: This method avoids additional API calls or database queries, ensuring optimal performance.
        """
        try:
            unique_categories = self.get_post_categories()

            if not unique_categories:
                return "No categories found"

            navbar_items = []

            for category in unique_categories.values():
                category_url = self.frontend_url + f"/category/{category.slug}"
                navbar_items.append(
                    f'<li><a href="{category_url}">{category.name}</a></li>'
                )

            navbar_html = (
                f'<nav class="dynamic-nav"><ul>{"".join(navbar_items)}</ul></nav>'
            )
            return navbar_html

        except Exception as e:
            print(f"Error creating navbar: {e}")
            return '<nav class="dynamic-nav"><ul><li>Error generating navbar</li></ul></nav>'

    def create(self, image_url: str, trend: str, affiliate_link: str = "") -> str:
        try:
            title = self.get_post_title(trend)
            content = self.get_post_content(title, trend, affiliate_link)
            featured_media_id = self.upload_feature_image(image_url) if image_url else 0

            tag_names = [trend.lower(), "affiliate", "ad"]
            tag_ids = []
            for tag_name in tag_names:
                tag_id = self.get_or_create_tag(tag_name)
                if tag_id:
                    tag_ids.append(tag_id)

            url = f"{self.api_url}/posts"
            payload = {
                "title": title,
                "content": content,
                "status": "publish",
                "featured_media": featured_media_id,
                "categories": [],
                "tags": tag_ids,
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
        try:
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            image_data = image_response.content

            url = f"{self.api_url}/media"
            headers = self.headers.copy()
            headers.pop("Content-Type", None)
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
        try:
            response = requests.get(
                f"{self.api_url}/tags",
                headers=self.headers,
                params={"search": tag_name},
            )
            response.raise_for_status()
            tags = response.json()
            for tag in tags:
                if tag["name"].lower() == tag_name.lower():
                    return tag["id"]
            response = requests.post(
                f"{self.api_url}/tags", headers=self.headers, json={"name": tag_name}
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
    posts = service.get_posts()
    print(f"Retrieved {len(posts)} posts.")
    for post in posts:
        for category in post.categories:
            print(
                f"Post ID: {post.id}, Category: {category.name}, Slug: {category.slug}"
            )
