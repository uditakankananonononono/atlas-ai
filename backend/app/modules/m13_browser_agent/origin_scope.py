"""Per-session origin scopes carried through reads, fills and approval clicks."""
from .security import NavigationBlocked, validate_public_url


class ScopedLocator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector

    async def fill(self, value):
        locator = self.page.raw.locator(self.selector)
        self.page.check()  # No intervening await before the actual write.
        result = await locator.fill(value)
        self.page.check()
        return result

    async def input_value(self):
        locator = self.page.raw.locator(self.selector)
        self.page.check()
        result = await locator.input_value()
        self.page.check()
        return result

    async def click(self):
        locator = self.page.raw.locator(self.selector)
        self.page.check()  # Also covers M02 final-submit engine.
        result = await locator.click()
        self.page.check()
        return result


class ScopedPage:
    def __init__(self, raw, hosts, blocked):
        self.raw, self.hosts, self.blocked = raw, hosts, blocked

    def check(self):
        if self.blocked():
            raise NavigationBlocked('platform session aborted after prohibited request')
        validate_public_url(self.raw.url, self.hosts)

    @property
    def url(self):
        self.check()
        return self.raw.url

    def locator(self, selector):
        self.check()
        return ScopedLocator(self, selector)

    async def goto(self, url, **kwargs):
        if self.blocked():
            raise NavigationBlocked('platform session aborted after prohibited request')
        validate_public_url(url, self.hosts)
        result = await self.raw.goto(url, **kwargs)
        self.check()
        return result

    async def content(self):
        self.check()
        result = await self.raw.content()
        self.check()
        return result

    async def screenshot(self, **kwargs):
        self.check()
        # Service uses locator objects as masks; unwrap only after validation.
        if 'mask' in kwargs:
            kwargs['mask'] = [self.raw.locator(x.selector) if isinstance(x, ScopedLocator) else x for x in kwargs['mask']]
        result = await self.raw.screenshot(**kwargs)
        self.check()
        return result
