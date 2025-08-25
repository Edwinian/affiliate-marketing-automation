import os
from dotenv import load_dotenv
import requests
from typing import List, Dict
import base64

from all_types import AffiliateLink, WordpressPost, WordpressCategory, WordpressTag
from channel import Channel
from enums import LlmErrorPrompt
from llm_service import LlmService

load_dotenv()


class WordpressService(Channel):
    POSTS: List[WordpressPost] = []
    TAGS: List[WordpressTag] = []

    def __init__(self):
        super().__init__()
        self.api_url = os.getenv("WORDPRESS_API_URL")
        self.frontend_url = os.getenv("WORDPRESS_FRONTEND_URL")
        username = os.getenv("WORDPRESS_USERNAME")
        app_password = os.getenv("WORDPRESS_APP_PASSWORD")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Basic {base64.b64encode(f'{username}:{app_password}'.encode()).decode()}",
        }

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
                self.logger.info(f"Fetching page {page} of {per_page} posts...")
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
            self.logger.error(
                f"Error retrieving posts: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Error parsing response: {e}")
            return []

    def get_unique_categories(self) -> Dict[str, WordpressCategory]:
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
            self.logger.error(f"Error retrieving categories: {e}")
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
            unique_categories = self.get_unique_categories()

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
            self.logger.error(f"Error creating navbar: {e}")
            return '<nav class="dynamic-nav"><ul><li>Error generating navbar</li></ul></nav>'

    def create(self, title: str, image_url: str, affiliate_link: AffiliateLink) -> str:
        try:
            content = self.get_post_content(title, affiliate_link)
            featured_media_id = self.upload_feature_image(image_url) if image_url else 0
            tag_ids = self.get_similar_tag_ids(title) or self.create_tags(title)

            url = f"{self.api_url}/posts"
            payload = {
                "title": title,
                "content": content,
                "status": "publish",
                "featured_media": featured_media_id,
                "categories": affiliate_link.categories,
                "tags": tag_ids,
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            post_data = response.json()
            id = post_data.get("id", "")
            return id
        except (requests.RequestException, ValueError) as e:
            self.logger.error(
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
            self.logger.error(
                f"Error uploading image: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return 0

    def get_tags(self, search: str = "") -> List[WordpressTag]:
        """
        Retrieve all tags from WordPress.
        Returns a list of WordpressTag objects.
        """
        if self.TAGS:
            return self.TAGS

        try:
            tags = []
            page = 1
            per_page = 100

            while True:
                self.logger.info(f"Fetching page {page} of {per_page} tags...")
                url = f"{self.api_url}/tags"
                params = {"page": page, "per_page": per_page, "search": search}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                page_tags = response.json()

                if not page_tags:
                    break

                for tag in page_tags:
                    tag_name = tag.get("name", "")
                    tag_id = tag.get("id", 0)
                    if tag_name and tag_id:
                        tags.append(WordpressTag(id=tag_id, name=tag_name))

                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1

            self.TAGS = tags
            return tags

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving tags: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Error parsing tags response: {e}")
            return []

    def get_similar_posts(
        self, title: str, posts: List[WordpressPost] = []
    ) -> List[WordpressPost]:
        try:
            all_posts = posts or self.get_posts()

            if not all_posts:
                return []

            # Select only id and title to reduce prompt size
            posts_with_id_and_title = [
                {"id": post.id, "title": post.title} for post in all_posts
            ]
            no_similar_prompt = "No similar posts found."
            similar_post_ids_str = self.llm_service.generate_text(
                f"Based on the title '{title}', find posts with similar title from the following list: {posts_with_id_and_title}. Return the IDs of the similar posts as a list separated by comma. If no similar posts are found, return '{no_similar_prompt}'."
            )
            similar_posts_found = no_similar_prompt not in similar_post_ids_str

            if not similar_posts_found:
                return []

            # LLM prompt length limit may be triggered, retry with fewer posts
            if LlmErrorPrompt.LENGTH_EXCEEDED in similar_post_ids_str:
                if len(all_posts) > 1:
                    trim_count = min(5, len(all_posts) - 1)
                    return self.get_similar_posts(
                        title=title, posts=all_posts[:-trim_count]
                    )
                else:
                    return []

            simila_posts = [
                post
                for post in all_posts
                if post.id in similar_post_ids_str and post.title != title
            ]
            return simila_posts
        except Exception as e:
            self.logger.error(f"Error finding similar posts: {e}")
            return []

    def get_similar_tag_ids(
        self, title: str, tags: List[WordpressTag] = []
    ) -> List[int]:
        try:
            all_tags = tags or self.get_tags()

            if not all_tags:
                return []

            no_similar_prompt = "No similar tags found."
            similar_tags = self.llm_service.generate_text(
                f"Based on the title '{title}', find similar tags from the following list: {all_tags}. Return the IDs of the similar tags as a list separated by comma to be split into a list later on. If no similar tags are found, return '{no_similar_prompt}'."
            )
            tag_ids_str = similar_tags.split(",")
            similar_tags_found = no_similar_prompt not in similar_tags

            if not similar_tags_found:
                return []

            if any([not tag_id.isdigit() for tag_id in tag_ids_str]):
                self.logger.info(
                    f"Invalid tag IDs found in response: {tag_ids_str}. Returning empty list."
                )
                return []

            # LLM prompt length limit may be triggered, retry with fewer tags
            if LlmErrorPrompt.LENGTH_EXCEEDED in similar_tags:
                if len(all_tags) > 1:
                    trim_count = min(5, len(all_tags) - 1)
                    return self.get_similar_tag_ids(
                        title=title, tags=all_tags[:-trim_count]
                    )
                else:
                    return []

            return [int(tag_id) for tag_id in tag_ids_str]
        except Exception as e:
            self.logger.error(f"Error finding similar tags: {e}")
            return []

    def create_tags(self, title: str) -> list[int]:
        try:
            tag_ids = []
            new_tags = self.llm_service.generate_text(
                f"Create 3 wordpress blog tags based on this title: {title}, return the tags only, separated by commas to be split into a list later on."
            ).split(",")

            for new_tag in new_tags:
                response = requests.post(
                    f"{self.api_url}/tags", headers=self.headers, json={"name": new_tag}
                )
                response.raise_for_status()
                tag_id = response.json().get("id", 0)
                tag_ids.append(tag_id)

            return tag_ids
        except requests.RequestException as e:
            self.logger.error(
                f"Error creating tag {title}: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return []

    def get_post_content(
        self, title: str, affiliate_link: AffiliateLink, paragraph_count: int = 3
    ) -> str:
        try:
            prompt = f"Give me a wordpress post content for the title {title}, including an introduction, {paragraph_count} paragraph{"s" if paragraph_count > 1 else ""} and a conclusion, 50-80 words for introduction and conclusion, 100-150 words for each paragraph, 2 empty lines to separate introduction and the first paragraph, 2 empty lines to separate conclusion and the last paragraph, 1 empty line to separate the paragraphs, return the post content only"
            content = self.llm_service.generate_text(prompt)
            similar_posts = self.get_similar_posts(title)

            if affiliate_link:
                content += f'\n\n<a href="{affiliate_link.url}" target="_blank" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Shop Now #ad</a>\n\n{self.DISCLOSURE}'

            if similar_posts:
                content += "\n\n<h2><strong>Related Posts</strong></h2>\n"
                for post in similar_posts:
                    content += f'<a href="{post.link}">{post.title}</a><br>\n'

            return content
        except Exception as e:
            self.logger.error(f"Error generating content: {e}")


if __name__ == "__main__":
    service = WordpressService()
    posts = service.get_posts()
    print(f"Retrieved {len(posts)} posts.")
    for post in posts:
        for category in post.categories:
            print(
                f"Post ID: {post.id}, Category: {category.name}, Slug: {category.slug}"
            )
