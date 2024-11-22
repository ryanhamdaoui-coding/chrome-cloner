import asyncio
from playwright.async_api import async_playwright

async def replicate_action(slave_pages, action_type, selector, value=None):
    for slave_page in slave_pages:
        try:
            if action_type == 'click':
                await slave_page.click(selector)
            elif action_type == 'input':
                await slave_page.fill(selector, value)
            elif action_type == 'scroll':
                await slave_page.evaluate(f"window.scrollTo({value['x']}, {value['y']})")
        except Exception as e:
            print(f"Failed to replicate {action_type} on {selector}: {e}")

async def track_and_replicate(master_page, slave_pages):
    await master_page.evaluate("""
        window.actions = [];
        document.addEventListener('click', (event) => {
            const selector = event.target.tagName.toLowerCase() +
                             (event.target.id ? `#${event.target.id}` : '') +
                             (event.target.className ? `.${event.target.className.replace(/\\s+/g, '.')}` : '');
            window.actions.push({ type: 'click', selector });
        });

        document.addEventListener('input', (event) => {
            const selector = event.target.tagName.toLowerCase() +
                             (event.target.id ? `#${event.target.id}` : '') +
                             (event.target.className ? `.${event.target.className.replace(/\\s+/g, '.')}` : '');
            window.actions.push({ type: 'input', selector, value: event.target.value });
        });

        document.addEventListener('scroll', () => {
            window.actions.push({ type: 'scroll', value: { x: window.scrollX, y: window.scrollY } });
        });
    """)

    while True:
        try:
            actions = await master_page.evaluate("window.actions.splice(0)")
            for action in actions:
                await replicate_action(slave_pages, action['type'], action.get('selector'), action.get('value'))
        except Exception as e:
            print(f"Error during replication: {e}")
        await asyncio.sleep(0.01)

async def replicate_url(master_page, slave_pages):
    last_url = master_page.url
    while True:
        current_url = master_page.url
        if current_url != last_url:
            for slave_page in slave_pages:
                await slave_page.goto(current_url)
            last_url = current_url
        await asyncio.sleep(0.1)

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        master_context = await browser.new_context()
        master_page = await master_context.new_page()
        await master_page.goto("https://google.com")

        slave_contexts = [await browser.new_context() for _ in range(5)]
        slave_pages = [await context.new_page() for context in slave_contexts]
        for slave_page in slave_pages:
            await slave_page.goto("https://google.com")

        url_task = asyncio.create_task(replicate_url(master_page, slave_pages))
        actions_task = asyncio.create_task(track_and_replicate(master_page, slave_pages))

        try:
            print("Perform actions in the master window to replicate them.")
            await asyncio.gather(url_task, actions_task)
        except asyncio.CancelledError:
            print("Stopping replication...")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
