import os
import html
from dotenv import load_dotenv
import requests
from typing import List

from all_types import (
    AffiliateLink,
    CreateChannelResponse,
    WordpressPost,
    WordpressCategory,
    WordpressTag,
)
from channel import Channel
from enums import LlmErrorPrompt

load_dotenv()


class WordpressService(Channel):
    CATEGORIES: List[WordpressCategory] = []
    POSTS: List[WordpressPost] = []
    TAGS: List[WordpressTag] = []

    def __init__(self):
        super().__init__()
        self.api_url = os.getenv("WORDPRESS_API_URL")
        self.frontend_url = os.getenv("WORDPRESS_FRONTEND_URL")
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.getenv('WORDPRESS_ACCESS_TOKEN')}",
        }

    def sanitize(self, title: str) -> str:
        # WP may replace spaces with non-breaking spaces
        return html.unescape(title).replace("\xa0", " ")

    def get_menus(self, params: dict[str, str] = None) -> List[dict]:
        """
        Retrieves all navigation menus from WordPress with pagination.
        """
        try:
            menus = []
            page = 1
            per_page = 100
            params = params or {}

            while True:
                self.logger.info(f"Fetching menus, page {page}...")
                params.update({"page": str(page), "per_page": str(per_page)})
                url = f"{self.api_url}/menus"
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                page_menus = response.json()

                if not page_menus:
                    break

                menus.extend(page_menus)

                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1

            self.logger.info(f"Retrieved {len(menus)} menus")
            return menus

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving menus: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Error parsing menus response: {e}")
            return []

    def get_homepage_menu(self) -> int | None:
        """
        Retrieves the menu ID for a navigation menu named 'Homepage' from WordPress.
        Uses the /wp/v2/menus endpoint to fetch all menus and searches for 'Homepage' (case-insensitive).
        """
        try:
            self.logger.info("Fetching menus to find 'Homepage' menu...")
            params = {"search": "Homepage"}
            menus = self.get_menus(params)
            menu_id = menus[0].get("id", 0) if menus else None

            if menu_id:
                self.logger.info(f"Found 'Homepage' menu with ID {menu_id}")
                return menu_id

            self.logger.info("No 'Homepage' menu found")

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving menus: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return None
        except ValueError as e:
            self.logger.error(f"Error parsing menus response: {e}")
            return None

    def create_homepage_menu(self) -> int:
        """
        Creates a 'Homepage' menu if it doesn't exist and returns its menu ID.
        Calls get_homepage_menu to check for an existing 'Homepage' menu.
        """
        try:
            # Create new 'Homepage' menu
            self.logger.info("Creating new 'Homepage' menu...")
            payload = {
                "name": "Homepage",
                "description": "Dynamic Homepage menu",
            }
            # WordPress.com may not support 'locations' in the POST payload
            # Try without 'locations' first
            response = requests.post(
                f"{self.api_url}/menus", headers=self.headers, json=payload
            )
            if response.status_code == 400:
                self.logger.warning(
                    "Menu creation failed, retrying without 'locations'..."
                )
                payload.pop("locations", None)
                response = requests.post(
                    f"{self.api_url}/menus", headers=self.headers, json=payload
                )

            response.raise_for_status()
            menu_data = response.json()
            menu_id = menu_data.get("id", 0)

            if menu_id:
                self.logger.info(f"Created 'Homepage' menu with ID {menu_id}")
                return menu_id
            else:
                self.logger.error(
                    "Failed to retrieve ID for newly created 'Homepage' menu"
                )
                return 0

        except requests.RequestException as e:
            self.logger.error(
                f"Error creating 'Homepage' menu: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return 0
        except ValueError as e:
            self.logger.error(
                f"Error parsing response for 'Homepage' menu creation: {e}"
            )
            return 0

    def get_homepage_menu_id(self) -> int:
        """
        Retrieves the menu ID for the 'Homepage' menu or creates it if it doesn't exist.

        Returns:
            int: Menu ID of the 'Homepage' menu, 0 on error.
        """
        try:
            menu_id = self.get_homepage_menu()
            if menu_id is not None:
                return menu_id
            return self.create_homepage_menu()
        except Exception as e:
            self.logger.error(f"Error in get_homepage_menu_id: {e}")
            return 0

    def get_menu_items(self, menu_id: int) -> List[str]:
        """
        Retrieves all navigation menu item titles for a specified menu from WordPress.
        Uses the /wp/v2/menu-items endpoint with pagination to fetch all items.
        """
        try:
            menu_items = []
            page = 1
            per_page = 100

            while True:
                self.logger.info(
                    f"Fetching page {page} of {per_page} menu items for menu ID {menu_id}..."
                )
                url = f"{self.api_url}/menu-items"
                params = {"menus": menu_id, "page": page, "per_page": per_page}
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                page_items = response.json()

                if not page_items:
                    break

                for item in page_items:
                    title = item.get("title", {}).get("rendered", "")
                    if title:
                        menu_items.append(self.sanitize(title))

                total_pages = int(response.headers.get("X-WP-TotalPages", 1))
                if page >= total_pages:
                    break
                page += 1

            self.logger.info(
                f"Retrieved {len(menu_items)} menu items for menu ID {menu_id}"
            )
            return menu_items

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving menu items for menu ID {menu_id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return []
        except ValueError as e:
            self.logger.error(
                f"Error parsing menu items response for menu ID {menu_id}: {e}"
            )
            return []

    def update_menu_items(self) -> List[int]:
        """
        Update menu items for categories not already in the 'Homepage' menu.
        """
        try:
            # Step 1: Get or create 'Homepage' menu
            menu_id = self.get_homepage_menu_id()

            if not menu_id:
                self.logger.error("Failed to get or create 'Homepage' menu, aborting")
                return []

            # Step 2: Get existing menu item titles
            menu_items = self.get_menu_items(menu_id)
            existing_titles = [title for title in menu_items]
            self.logger.info(f"Existing menu item titles: {existing_titles}")

            # Step 3: Get all categories
            categories = self.get_categories()

            if not categories:
                self.logger.info("No categories found to create menu items")
                return []

            self.logger.info(f"Categories: {[cat.name for cat in categories]}")

            # Step 4: Filter categories not in menu
            new_categories = [
                cat for cat in categories if cat.name not in existing_titles
            ]
            if not new_categories:
                self.logger.info(f"All categories already in menu ID {menu_id}")
                return []

            self.logger.info(f"New categories: {[cat.name for cat in new_categories]}")

            # Step 5: Create menu items for missing categories
            menu_order = len(existing_titles) + 1
            new_menu_ids = []

            for category in sorted(new_categories, key=lambda x: x.name.lower()):
                category_name = category.name
                category_url = f"{self.frontend_url}/category/{category.slug}"
                payload = {
                    "title": category_name,
                    "url": category_url,
                    "menu_order": menu_order,
                    "status": "publish",
                    "type": "custom",  # Custom link for category archive
                    "object": "category",  # Reference to category
                    "object_id": category.id,  # Category ID
                    "menus": menu_id,  # Assign to specified menu
                }
                self.logger.info(f"Creating menu item with payload: {payload}")
                response = requests.post(
                    f"{self.api_url}/menu-items", headers=self.headers, json=payload
                )
                response.raise_for_status()
                menu_item_id = response.json().get("id", 0)

                if menu_item_id:
                    self.logger.info(
                        f"Created menu item '{category_name}' (ID: {menu_item_id}) for menu ID {menu_id}"
                    )
                    menu_order += 1
                    new_menu_ids.append(menu_item_id)
                else:
                    self.logger.error(
                        f"Failed to create menu item for category '{category_name}'"
                    )

            self.logger.info(
                f"Added {len(new_categories)} new menu items to menu ID {menu_id}"
            )
            return new_menu_ids

        except requests.RequestException as e:
            self.logger.error(
                f"Error creating menu items for menu ID {menu_id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Error parsing response for menu items creation: {e}")
            return []

    def create_category(self, name: str, slug: str = "", description: str = "") -> int:
        try:
            name = name.strip()
            self.logger.info(f"Creating category with name: {name}")

            url = f"{self.api_url}/categories"
            payload = {"name": name, "slug": slug, "description": description}
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()

            category_data = response.json()
            category_id = category_data.get("id", 0)

            if category_id:
                self.logger.info(
                    f"Successfully created category '{name}' with ID: {category_id}"
                )
            else:
                self.logger.error(f"Failed to retrieve ID for category '{name}'")

            return category_id

        except requests.RequestException as e:
            self.logger.error(
                f"Error creating category '{name}': {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return 0
        except ValueError as e:
            self.logger.error(f"Error parsing response for category '{name}': {e}")
            return 0

    def get_categories(self) -> List[WordpressCategory]:
        if self.CATEGORIES:
            self.CATEGORIES

        url = f"{self.api_url}/categories"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        categories = response.json() if response else []
        self.CATEGORIES = [
            WordpressCategory(
                id=cat.get("id", 0),
                name=self.sanitize(cat.get("name", "")),
                slug=cat.get("slug", ""),
            )
            for cat in categories
        ]
        self.logger.info(f"Retrieved {len(self.CATEGORIES)} categories")
        return self.CATEGORIES

    def get_category_ids(self, query_names: List[str]) -> List[int]:
        try:
            query_names = [
                name.strip().lower() for name in query_names if name.strip()
            ]  # Normalize names
            categories = self.get_categories()
            query_categories = [
                cat for cat in categories if cat.name.lower() in query_names
            ]

            return [cat.id for cat in query_categories]

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving categories: {e}, Response: {e.response.text if e.response else 'No response'}"
            )
            return []
        except ValueError as e:
            self.logger.error(f"Error parsing categories response: {e}")
            return []

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
                                            name=self.sanitize(term.get("name", "")),
                                            slug=term.get("slug", ""),
                                        )
                                    )

                    post_data = WordpressPost(
                        id=post.get("id", 0),
                        title=self.sanitize(post.get("title", {}).get("rendered", "")),
                        content=self.sanitize(
                            post.get("content", {}).get("rendered", "")
                        ),
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

    def get_navbar_html(self) -> str:
        """
        Create a navigation bar with a tab for each unique category from existing blog posts.
        Returns an HTML string representing the navbar, with each tab linking to the category archive page.

        Usage: Manually Add Navbar HTML to Theme Files

        To integrate the generated navbar HTML into your WordPress.com site, follow these steps:
        1. **Generate the Navbar HTML**:
           - Run this method (e.g., via a local Python script or AWS Lambda) to obtain the HTML string.
           - Example command: `python script.py`
           - Example output: `<nav class="dynamic-nav"><ul><li><a href="https://edwinchan6.wordpress.com/category/anime">Anime</a></li><li><a href="https://edwinchan6.wordpress.com/category/trends">Trends</a></li></ul></nav>`
           - Copy the HTML string from the console or log output.

        2. **Access Theme Files**:
           - Log in to your WordPress.com admin panel (e.g., https://edwinchan6.wordpress.com/wp-admin).
           - Navigate to **Appearance > Theme Editor** to edit your active theme's files (if available, requires Business plan or higher).
           - Alternatively, use a Custom HTML widget in **Appearance > Widgets** or **Appearance > Customize**.
           - Note: WordPress.com restricts theme file editing on Free/Personal plans. Upgrade to Business if needed.

        3. **Edit the Theme or Widget**:
           - If theme editing is available, open `header.php` in the Theme Editor.
           - Locate the navigation menu section (e.g., within `<header>` or `<nav>` tags).
           - Add the copied navbar HTML. Example:
             ```php
             <header>
                 <!-- Dynamic Navbar -->
                 <nav class="dynamic-nav">
                     <ul>
                         <li><a href="https://edwinchan6.wordpress.com/category/anime">Anime</a></li>
                         <li><a href="https://edwinchan6.wordpress.com/category/trends">Trends</a></li>
                     </ul>
                 </nav>
             </header>
             ```
           - If theme editing is restricted, add the HTML to a Custom HTML widget in **Appearance > Widgets** or **Customize > Widgets**.
           - Save changes.

        4. **Verify the Navbar**:
           - Visit your site (e.g., https://edwinchan6.wordpress.com) to ensure the navbar appears correctly.
           - Click each category link to confirm it loads the correct category archive page.
           - If the navbar doesn’t display, check for theme-specific CSS conflicts or widget placement.

        5. **Update Process**:
           - When new categories are added, rerun this method to generate updated HTML.
           - Update the Custom HTML widget or theme file manually.
           - Frequency: Suitable for infrequent updates. For frequent changes, consider manual menu management via **Appearance > Menus**.

        6. **Notes**:
           - **Plan Limitations**: Free/Personal plans may restrict theme editing. Use a Custom HTML widget or upgrade to Business.
           - **Permalinks**: The `link` field ensures correct category URLs (e.g., `https://edwinchan6.wordpress.com/category/anime`).
           - **Backup**: Save a copy of the HTML before making changes.
           - **Performance**: This method avoids API calls during page loads, ensuring optimal performance.
        """
        try:
            categories = self.get_categories()

            if not categories:
                return "No categories found"

            navbar_items = []

            for category in categories:
                category_url = f"{self.frontend_url}/category/{category.slug}"
                navbar_items.append(
                    f'<li><a href="{category_url}">{self.sanitize(category.name)}</a></li>'
                )

            navbar_html = (
                f'<nav class="dynamic-nav"><ul>{"".join(navbar_items)}</ul></nav>'
            )
            return navbar_html

        except Exception as e:
            self.logger.error(f"Error creating navbar: {e}")
            return '<nav class="dynamic-nav"><ul><li>Error generating navbar</li></ul></nav>'

    def create(
        self, title: str, image_url: str, affiliate_link: AffiliateLink
    ) -> CreateChannelResponse:
        try:
            content = self.get_post_content(title, affiliate_link)
            featured_media_id = self.upload_feature_image(image_url) if image_url else 0
            category_ids = self.get_category_ids(affiliate_link.categories) or [
                self.create_category(name) for name in affiliate_link.categories
            ]
            tag_ids = self.get_similar_tag_ids(title) or self.create_tags(title)

            url = f"{self.api_url}/posts"
            payload = {
                "title": title,
                "content": content,
                "status": "publish",
                "featured_media": featured_media_id,
                "categories": category_ids,
                "tags": tag_ids,
            }
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            post_data = response.json()
            id = post_data.get("id", "")
            link = post_data.get("link", "")

            return CreateChannelResponse(id=id, url=link)
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

            similar_posts = [
                post
                for post in all_posts
                if str(post.id) in similar_post_ids_str and post.title != title
            ]
            return similar_posts
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

    def create_tags(self, title: str) -> List[int]:
        try:
            tag_ids = []
            new_tags = self.llm_service.generate_text(
                f"Create 3 wordpress blog tags based on this title: {title}, return the tags only, separated by commas to be split into a list later on."
            ).split(",")

            for new_tag in new_tags:
                self.logger.info(f"Creating tag: {new_tag.strip()}")
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
            prompt_splits = [
                f"Give me a wordpress post content for the title {title}, including an introduction, {paragraph_count} paragraphs and a conclusion",
                f"50-80 words for introduction and conclusion, 100-150 words for each paragraph",
                f"2 empty lines to separate introduction and the first paragraph, 2 empty lines to separate conclusion and the last paragraph, 1 empty line to separate the paragraphs",
                f"Each paragraph is preceded by a title that summarizes the paragraph wrapped with the <h3><b></b></h3> tag instead of the <p></p> tag",
                f"The last paragraph relates the content to {affiliate_link.product_title}, and explain why it is a good choice",
                f"The conclusion should include a call to action",
                f"Return the post content only",
            ]
            prompt = ". ".join(prompt_splits)
            content = self.llm_service.generate_text(prompt)
            similar_posts = self.get_similar_posts(title)

            if affiliate_link:
                content += f'\n\n<a href="{affiliate_link.url}" target="_blank" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">Shop Now</a>\n\n<small>{self.DISCLOSURE}</small>'

            if similar_posts:
                content += "\n\n<h4><strong>Related Posts</strong></h4>\n"
                for post in similar_posts:
                    content += (
                        f'<a href="{post.link}" target="_blank">{post.title}</a><br>\n'
                    )

            return content
        except Exception as e:
            self.logger.error(f"Error generating content: {e}")
            return ""


if __name__ == "__main__":
    service = WordpressService()
    new_menu_ids = service.update_menu_items()
    print(f"Created menu items: {new_menu_ids}")

    # html_content = service.get_navbar_html()
    # print(f"Navbar HTML:\n{html_content}")
