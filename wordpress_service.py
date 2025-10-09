import base64
import html
from urllib.error import HTTPError
import requests
from typing import List, Optional

from all_types import (
    AffiliateLink,
    CreateChannelResponse,
    WordpressPost,
    WordpressCategory,
    WordpressTag,
)
from channel import Channel
from constants import PROMPT_SPLIT_JOINER
from enums import LlmErrorPrompt, WordpressPostStatus

from common import os, load_dotenv, requests
from utils import get_img_element, get_with_retry


class WordpressService(Channel):
    CATEGORIES: List[WordpressCategory] = []
    POSTS: List[WordpressPost] = []
    TAGS: List[WordpressTag] = []

    def __init__(self, credentials: dict[str, str], is_wordpress_hosted: bool = True):
        super().__init__()
        self.api_url = credentials["API_URL"]
        self.frontend_url = credentials["FRONTEND_URL"]
        self.headers = self.get_headers(credentials)
        self.is_wordpress_hosted = is_wordpress_hosted

    def get_headers(self, credentials: dict[str, str]):
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "affiliate_marketing_automation/1.0",
        }
        access_token = credentials.get("ACCESS_TOKEN", None)
        username = credentials.get("USERNAME", None)
        app_password = credentials.get("APP_PASSWORD", None)

        if all([not access_token, any([not username, not app_password])]):
            self.logger.error(
                "No authentication method provided. Please set ACCESS_TOKEN for JWT auth or USERNAME and APP_PASSWORD for Basic auth."
            )
            return headers

        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        else:
            username = credentials.get("USERNAME")
            app_password = credentials.get("APP_PASSWORD")
            auth_string = f"{username}:{app_password}"
            encoded_auth = base64.b64encode(auth_string.encode()).decode()
            headers["Authorization"] = f"Basic {encoded_auth}"

        return headers

    def sanitize(self, title: str) -> str:
        # WP may replace spaces with non-breaking spaces
        return html.unescape(title).replace("\xa0", " ")

    def update_nav_menu(self, menu_id: int = 2) -> List[int]:
        """
        Update navigation menu by adding missing categories that don't exist in the menu items.

        Args:
            menu_id (int): The ID of the menu to update. Defaults to 2.

        Returns:
            List[int]: List of IDs of newly created menu items.
        """
        try:
            # Step 1: Get all categories except "Uncategorized", which is set by WordPress
            categories = self.get_categories()
            categories = [cat for cat in categories if cat.name != "Uncategorized"]

            if not categories:
                self.logger.info("No categories found to update menu")
                return []

            category_names = [cat.name for cat in categories]
            self.logger.info(
                f"Found {len(category_names)} categories: {category_names}"
            )

            # Step 2: Get existing menu items and extract titles
            menu_items = self.get_menu_items(menu_id)
            existing_titles = []

            if not menu_items:
                self.logger.info(f"No existing menu items found for menu ID {menu_id}")
            else:
                existing_titles = [item["title"]["rendered"] for item in menu_items]
                self.logger.info(f"Existing menu titles: {existing_titles}")

            # Step 3: Find missing categories (categories not in menu items)
            missing_categories = [
                cat for cat in categories if cat.name not in existing_titles
            ]

            if not missing_categories:
                self.logger.info(
                    f"All {len(category_names)} categories already exist in menu ID {menu_id}"
                )
                return []

            self.logger.info(
                f"Found {len(missing_categories)} missing categories: {[cat.name for cat in missing_categories]}"
            )

            # Step 4: Add missing categories to menu items
            new_menu_ids = []
            menu_order = len(menu_items) + 1  # Start after existing items

            for category in sorted(missing_categories, key=lambda x: x.name.lower()):
                category_name = category.name
                category_url = f"{self.frontend_url}/category/{category.slug}"

                payload = {
                    "title": category_name,
                    "url": category_url,
                    "menu_order": menu_order,
                    "status": "publish",
                    "type": "taxonomy",
                    "object": "category",  # Reference to category
                    "object_id": category.id,  # Category ID
                    "menus": menu_id,  # Assign to specified menu
                }

                self.logger.info(
                    f"Creating menu item for category '{category_name}' with payload: {payload}"
                )

                try:
                    response = requests.post(
                        f"{self.api_url}/menu-items", headers=self.headers, json=payload
                    )
                    response.raise_for_status()
                    menu_item_data = response.json()
                    menu_item_id = menu_item_data.get("id", 0)

                    if menu_item_id:
                        self.logger.info(
                            f"Successfully created menu item '{category_name}' (ID: {menu_item_id}) "
                            f"for menu ID {menu_id}"
                        )
                        new_menu_ids.append(menu_item_id)
                        menu_order += 1
                    else:
                        self.logger.error(
                            f"Failed to retrieve ID for menu item '{category_name}' - response: {menu_item_data}"
                        )

                except requests.RequestException as e:
                    self.logger.error(
                        f"Error creating menu item for category '{category_name}': {e}, "
                        f"Response: {e.response.text if e.response else 'No response'}, "
                        f"Status Code: {e.response.status_code if e.response else 'N/A'}"
                    )
                except ValueError as e:
                    self.logger.error(
                        f"Error parsing response for menu item '{category_name}': {e}"
                    )

            if new_menu_ids:
                self.logger.info(
                    f"Successfully added {len(new_menu_ids)} new menu items to menu ID {menu_id}: {new_menu_ids}"
                )
            else:
                self.logger.warning("No new menu items were created")

            return new_menu_ids

        except Exception as e:
            self.logger.error(
                f"Unexpected error in update_nav_menu for menu ID {menu_id}: {e}"
            )
            return []

    def get_menus(self, params: dict[str, str] = {}) -> List[dict]:
        """
        Retrieves all navigation menus from WordPress with pagination.
        """
        try:
            menus = self._get_data(resource="menus", more_params=params)
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
            params = {"menus": menu_id}
            menu_items = self._get_data(resource="menu-items", more_params=params)
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

    def update_menu_items(self, menu_id: int) -> List[int]:
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

    @get_with_retry(
        max_retries=5,
        initial_delay=2.0,
        max_delay=30.0,
        retry_on_exceptions=(
            ValueError,
            ConnectionError,
            HTTPError,
        ),
    )
    def _get_data(
        self,
        resource: str,
        page: int = 1,
        all_responses: Optional[List[dict]] = None,
        more_params: Optional[dict] = {},
    ) -> List[dict]:
        per_page = 100
        params = {"page": page, "per_page": per_page, **more_params}

        url = f"{self.api_url}/{resource}"

        self.logger.info(f"Fetching {resource}, page {page}...")
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        responses = response.json() if response else []

        if all_responses is None:  # Initialize fresh list for each new fetch
            all_responses = []

        all_responses += responses

        # Fetch more when item count >= page size
        if len(responses) >= per_page:
            return self._get_data(
                resource=resource,
                page=page + 1,
                all_responses=all_responses,
                more_params=more_params,
            )

        self.logger.info(f"Retrieved {len(all_responses)} {resource} items")
        return all_responses

    def get_categories(self) -> List[WordpressCategory]:
        if self.CATEGORIES:
            return self.CATEGORIES

        data = self._get_data(resource="categories")
        self.CATEGORIES = [
            WordpressCategory(
                id=cat.get("id", 0),
                name=self.sanitize(cat.get("name", "")),
                slug=cat.get("slug", ""),
            )
            for cat in data
        ]
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
            params = {
                "_embed": "wp:term",
                "status": "publish,future,draft,pending,private",  # Get all post statuses
            }
            page_posts = self._get_data(resource="posts", more_params=params)

            if not page_posts:
                return []

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
                    content=self.sanitize(post.get("content", {}).get("rendered", "")),
                    link=post.get("link", ""),
                    date=post.get("date", ""),
                    status=post.get("status", ""),
                    featured_media=post.get("featured_media", 0),
                    categories=categories,
                )
                posts.append(post_data)

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

    def get_wordpress_title(self, affiliate_link: AffiliateLink) -> str:
        all_posts = self.get_posts()
        # Titles of posts in categories matching the affiliate link's categories
        category_titles = [
            post.title
            for post in all_posts
            if post.categories
            and any(
                link_cat
                for link_cat in affiliate_link.categories
                if link_cat in [cat.name for cat in post.categories]
            )
        ]
        title = self.get_title(
            affiliate_link=affiliate_link, category_titles=category_titles
        )

        return title

    def get_or_create_categories(self, affiliate_link: AffiliateLink) -> List[int]:
        category_ids = []

        for cat in affiliate_link.categories:
            cat_ids = self.get_category_ids([cat])

            if not cat_ids:
                cat_id = self.create_category(name=cat)
                cat_ids.append(cat_id)

            category_ids.append(cat_ids[0])

        return category_ids

    def delete_media(self, media_id: int) -> bool:
        """
        Delete a WordPress media item by its ID.

        Args:
            media_id (int): The ID of the media item to delete.

        Returns:
            bool: True if the media item was successfully deleted, False otherwise.
        """
        try:
            if not media_id:
                self.logger.warning("No media ID provided")
                return False

            url = f"{self.api_url}/media/{media_id}"
            response = requests.delete(
                url, headers=self.headers, params={"force": True}
            )
            response.raise_for_status()
            self.logger.info(f"Successfully deleted media item ID {media_id}")
            return True

        except requests.RequestException as e:
            self.logger.error(
                f"Error deleting media item ID {media_id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return False
        except ValueError as e:
            self.logger.error(
                f"Error parsing response for media item ID {media_id}: {e}"
            )
            return False

    def delete_post(self, post: WordpressPost) -> List[int]:
        """
        Delete multiple WordPress posts by their IDs.

        Args:
            post_ids (List[int]): List of post IDs to delete.

        Returns:
            List[int]: List of successfully deleted post IDs.
        """
        post_id = post.id

        try:
            url = f"{self.api_url}/posts/{post_id}"
            response = requests.delete(url, headers=self.headers)
            response.raise_for_status()
            deleted_id = post_id
            self.logger.info(f"Successfully deleted post ID {post_id}")
            # Clear cached posts to ensure consistency
            self.POSTS = []
        except requests.RequestException as e:
            self.logger.error(
                f"Error deleting post ID {post_id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
        except ValueError as e:
            self.logger.error(f"Error parsing response for post ID {post_id}: {e}")

        if deleted_id:
            self.delete_media(post.featured_media)
            self.logger.info(f"Successfully deleted posts: {deleted_id}")
        else:
            self.logger.warning("No posts were deleted")

        return deleted_id

    def update_post(self, post: WordpressPost) -> bool:
        """
        Update an existing WordPress post with the provided WordpressPost object.

        Args:
            post (WordpressPost): The WordPress post object containing updated data.

        Returns:
            bool: True if the post was successfully updated, False otherwise.
        """
        try:
            if not post.id:
                self.logger.error("No post ID provided for update")
                return False

            url = f"{self.api_url}/posts/{post.id}"
            payload = {
                "title": post.title,
                "content": post.content,
                "status": post.status,
                "featured_media": post.featured_media,
                "categories": (
                    [cat.id for cat in post.categories] if post.categories else []
                ),
                "excerpt": post.title,  # Avoid auto comments by WP
            }

            self.logger.info(f"Updating post ID {post.id} with payload: {payload}")
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()

            # Clear cached posts to ensure consistency
            self.POSTS = []
            self.logger.info(f"Successfully updated post ID {post.id}")
            return True

        except requests.RequestException as e:
            self.logger.error(
                f"Error updating post ID {post.id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return False
        except ValueError as e:
            self.logger.error(f"Error parsing response for post ID {post.id}: {e}")
            return False

    def create(
        self,
        affiliate_link: AffiliateLink,
    ) -> CreateChannelResponse:
        try:
            paragraph_count = 3
            # Images for body paragraphs and feature image
            image_urls = self.media_service.get_image_urls(
                query=affiliate_link.categories[0],
                limit=paragraph_count + 1,
                size="landscape",
            )

            if len(image_urls) < 1:
                self.logger.warning(
                    f"Insufficient images found for categories {affiliate_link.categories}, aborting post creation"
                )
                return ""

            title = self.get_wordpress_title(affiliate_link)
            content = self.get_post_content(
                title=title,
                affiliate_link=affiliate_link,
                image_urls=image_urls,
                paragraph_count=paragraph_count,
            )
            featured_media_id = self.upload_feature_image(
                image_url=image_urls[-1], title=title
            )
            category_ids = self.get_or_create_categories(affiliate_link)
            tag_ids = self.get_similar_tag_ids(title) + self.create_tags(
                affiliate_link
            )
            url = f"{self.api_url}/posts"
            status = (
                WordpressPostStatus.PENDING.value
                if self.is_wordpress_hosted
                else WordpressPostStatus.PUBLISH.value
            )

            # Author is the display name of the user
            payload = {
                "title": title,
                "content": content,
                "status": status,
                "featured_media": featured_media_id,
                "categories": category_ids,
                "tags": tag_ids,
                "excerpt": title,  # Avoid auto comments by WP
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

    def get_media(self, media_id: int) -> str:
        """
        Retrieve the media URL for a given media ID.

        Args:
            media_id (int): The WordPress media attachment ID

        Returns:
            str: The source URL of the image, or empty string if not found
        """
        try:
            if not media_id:
                self.logger.warning("No media ID provided")
                return ""

            # Get the media item by ID
            response = requests.get(
                f"{self.api_url}/media/{media_id}", headers=self.headers
            )
            response.raise_for_status()

            media_data = response.json()
            image_url = media_data.get("source_url", "")

            if image_url:
                self.logger.info(
                    f"Retrieved image URL for media ID {media_id}: {image_url}"
                )
            else:
                self.logger.warning(f"No source_url found for media ID {media_id}")

            return image_url

        except requests.RequestException as e:
            self.logger.error(
                f"Error retrieving image for media ID {media_id}: {e}, "
                f"Response: {e.response.text if e.response else 'No response'}, "
                f"Status Code: {e.response.status_code if e.response else 'N/A'}"
            )
            return ""
        except ValueError as e:
            self.logger.error(f"Error parsing media response for ID {media_id}: {e}")
            return ""

    def upload_feature_image(self, image_url: str, title: str) -> int:
        try:
            image_response = requests.get(image_url)
            image_response.raise_for_status()
            image_data = image_response.content

            url = f"{self.api_url}/media"
            headers = self.headers.copy()
            headers.pop("Content-Type", None)
            files = {"file": ("image.jpg", image_data, "image/jpeg")}
            response = requests.post(
                url,
                headers=headers,
                files=files,
                data={
                    "title": title,
                    "alt_text": title,
                    "description": title,
                },  # Add title to media metadata for SEO
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
            params = {"search": search}
            page_tags = self._get_data(resource="tags", more_params=params)
            tags = [
                WordpressTag(id=tag.get("id", 0), name=tag.get("name", ""))
                for tag in page_tags
            ]
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
        self, title: str, posts: List[WordpressPost] = [], limit=5
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
                f"Based on the title '{title}', find posts with similar title from the following list: {posts_with_id_and_title}. Return the IDs of the similar posts as a list separated by comma, sorted by highest similarity. If no similar posts are found, return '{no_similar_prompt}'."
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
            return similar_posts[:limit]
        except Exception as e:
            self.logger.error(f"Error finding similar posts: {e}")
            return []

    def get_similar_tag_ids(
        self, title: str, tags: List[WordpressTag] = [], limit=2
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
                        title=title, tags=all_tags[:-trim_count], limit=limit
                    )
                else:
                    return []
            
            ids = [int(tag_id) for tag_id in tag_ids_str]
            return ids[:limit]
        except Exception as e:
            self.logger.error(f"Error finding similar tags: {e}")
            return []

    def create_tags(self, affiliate_link: AffiliateLink, limit=3) -> List[int]:
        tag_ids = []
        new_tags = self.get_keywords(affiliate_link=affiliate_link, limit=limit)
        
        for new_tag in new_tags:
            try:
                self.logger.info(f"Creating tag: {new_tag.strip()}")
                response = requests.post(
                    f"{self.api_url}/tags", headers=self.headers, json={"name": new_tag}
                )
                response.raise_for_status()
                tag_id = response.json().get("id", 0)
                tag_ids.append(tag_id)
            except requests.RequestException as e:
                # Tags may already exist, try fetching existing tag ID
                all_tags = self.get_tags(new_tag)
                tag = next((t for t in all_tags if t.name == new_tag), None)

                if tag:
                    tag_ids.append(tag.id)
                else:
                    self.logger.error(
                        f"Error creating tag {affiliate_link.product_title}: {e}, Response: {e.response.text if e.response else 'No response'}"
                    )
                continue

        return tag_ids

    def _get_cta_content(self, affiliate_link: AffiliateLink) -> str:
        style = "margin-top: 20px;"

        def _get_a_tag_cta_content(children: str, style: Optional[str] = None) -> str:
            return f'\n\n<a href="{affiliate_link.url}" target="_blank" style="{style}">{children}</a>'

        if affiliate_link.cta_image_url:
            cta_image = (
                f'<img decoding="async" src="{affiliate_link.cta_image_url}" '
                f'alt="CTA" style="max-width: 100%; height: auto; display: block; cursor: pointer;" />'
            )

            # Wordpress-hostes Wordpress sanitizes onClick attribute from div element, instead wrap img element with a-tag
            # Self-hosted Wordpress does not render img element wrapped with a-tag, instead create clickable div with onclick that opens in new tab
            if self.is_wordpress_hosted:
                cta_content = _get_a_tag_cta_content(children=cta_image, style=style)
            else:
                cta_content = (
                    f"\n\n<div style='{style}' onclick=\"window.open('{affiliate_link.url}', '_blank')\">"
                    f"{cta_image}"
                    f"</div>"
                )
        else:
            # Fallback to regular button for text-only CTA
            style += " background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;"
            cta_content = _get_a_tag_cta_content(
                children=affiliate_link.cta_btn_text or "Shop Now", style=style
            )

        return cta_content

    def get_similar_posts_content(self, title: str) -> str:
        content = ""
        similar_posts = self.get_similar_posts(title)

        if similar_posts:
            content = "<h4><strong>Related Posts</strong></h4>\n"
            for post in similar_posts:
                content += (
                    f'<a href="{post.link}" target="_blank">{post.title}</a><br>\n'
                )

        return content

    def _get_social_media_content(
        self, affiliate_link: AffiliateLink, title: str
    ) -> str:
        common_style = {
            "height": "25px",
        }
        buttons = [
            {
                "redirect_url": "https://www.facebook.com/sharer/sharer.php?u={url}",
                "img_src": "https://webshielddaily.com/wp-content/uploads/2025/09/facebook.png",
                "alt": "Facebook",
                "color": "#3b5998",
            },
            {
                "redirect_url": "https://twitter.com/intent/tweet?url={url}&text={title}",
                "img_src": "https://webshielddaily.com/wp-content/uploads/2025/09/twitter.png",
                "alt": "X_Twitter",
                "color": "#1DA1F2",
            },
            {
                "redirect_url": "https://www.linkedin.com/sharing/share-offsite/?url={url}",
                "img_src": "https://webshielddaily.com/wp-content/uploads/2025/09/linkedin.png",
                "alt": "Linkedin",
                "color": "#0077b5",
            },
            {
                "redirect_url": "https://pinterest.com/pin/create/button/?url={url}&description={title}",
                "img_src": "https://webshielddaily.com/wp-content/uploads/2025/09/pinterest.png",
                "alt": "Pinterest",
                "color": "#BD081C",
            },
        ]

        # Generate button HTML dynamically
        buttons_html = []
        for button in buttons:
            # Format the URL with actual values
            url = button["redirect_url"].format(url=affiliate_link.url, title=title)

            button_html = (
                f'<a href="{url}" target="_blank" rel="noopener" style="margin-right: 10px; color: {button["color"]};">'
                f'{get_img_element(src=button["img_src"], alt=button["alt"], style=common_style)}'
                f"</a>"
            )
            buttons_html.append(button_html)

        # Join all buttons and create the container
        buttons_content = "".join(buttons_html)

        return (
            f"<h4><strong>Share With Friends</strong></h4>\n"
            f'<div class="social-share" style="margin-top: 20px; display: flex; flex-direction: row; align-items: center;">'
            f"{buttons_content}"
            f"</div>"
        )

    def get_post_content(
        self,
        title: str,
        affiliate_link: AffiliateLink,
        image_urls: list[str],
        paragraph_count: int = 3,
    ) -> str:
        try:
            prompt_splits = [
                f"Give me a wordpress post content for the title {title} that is SEO friendly, including an introduction, {paragraph_count} body paragraphs, and a conclusion",
                f"2 empty lines to separate introduction and the first body paragraph, 2 empty lines to separate conclusion and the last paragraph, 1 empty line to separate the body paragraphs",
                f"Each body paragraph is preceded by a title that summarizes the paragraph wrapped with the <h3><b></b></h3> tag instead of the <p></p> tag",
                f"The conclusion is peceded by a title that emphasizes it is a good choice",
                f"The conclusion relates the content to {affiliate_link.product_title} and explains why it is a good choice",
                f"The conclusion should include a strong call to action to help boost conversions",
                f"100 words for introduction and conclusion, 150 words for each body paragraph and the call to action",
                f"Limit sentences to no more than 20 words",
                f"30% of the sentences contain transition words, but do not start the introduction, body paragraphs and conclusion with them",
                f"Target audience is anyone who could use {affiliate_link.product_title}",
                f"Do not mention about contacting us for details as we do not work for the company of {affiliate_link.product_title}",
                f"Return the post content only",
            ]

            if image_urls:
                prompt_splits.append(
                    f"Add these images in front of each body paragraph respectively, wrapped with the <img> tag with style 'max-width: 100%; height: auto; display: block;': {', '.join(image_urls[:paragraph_count])}",
                )

            prompt = PROMPT_SPLIT_JOINER.join(prompt_splits)
            content = self.llm_service.generate_text(prompt)

            if affiliate_link.wordpress_content:
                content += f"\n\n{affiliate_link.wordpress_content}"

            if affiliate_link.video_ids:
                for id in affiliate_link.video_ids:
                    content += f'\n\n[video id="{id}"]'

            if affiliate_link.video_urls:
                for url in affiliate_link.video_urls:
                    content += f'\n\n<video controls style="max-width: 100%; height: auto; display: block;"><source src="{url}" type="video/mp4">Your browser does not support the video tag.</video>'

            cta_content = self._get_cta_content(affiliate_link)
            content += f"{cta_content}"
            content += f"\n\n<small>{self.DISCLOSURE}</small>"

            # Add social media share buttons
            social_media_content = self._get_social_media_content(affiliate_link, title)
            content += f"\n\n{social_media_content}"

            ## Use Wordpress option instead to reduce prompt usage
            # # Add related posts if any
            # similar_posts_content = self.get_similar_posts_content(title)
            # content += f"\n\n{similar_posts_content}"

            return content
        except Exception as e:
            self.logger.error(f"Error generating content: {e}")
            return ""


if __name__ == "__main__":
    credentials = {
        "API_URL": os.getenv("WORDPRESS_API_URL_VPN"),
        "ACCESS_TOKEN": os.getenv("WORDPRESS_ACCESS_TOKEN_VPN"),
        "FRONTEND_URL": os.getenv("WORDPRESS_FRONTEND_URL_VPN"),
    }
    service = WordpressService(credentials=credentials)
    items = service.get_posts()
    # post = items[0]
    # result = service.delete_post(post=post)
    print(f"result: {items[0].date}")

    # html_content = service.get_navbar_html()
    # print(f"Navbar HTML:\n{html_content}")
