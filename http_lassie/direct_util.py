import aiohttp
import asyncio
import async_timeout


async def fetch_and_save(session, url, output_path,
                         chunk_size=1024, timeout=10):
    bytes_read = 0

    with async_timeout.timeout(timeout):
        async with session.get(url) as response:
            # Don't save files that return a bad response.
            if response.status != 200:
                msg = "Response status for {} is {}"
                raise ValueError(msg.format(url, response.status))

            # Write the file to the output, streaming.
            with open(output_path, "wb") as fp:
                async for data in response.content.iter_chunked(chunk_size):
                    fp.write(data)
                    bytes_read += len(data)

    return url, output_path, bytes_read


async def fetch_and_save_all(loop, session,
                             *url_and_output_path_pairs,
                             **kwargs):
    async with session:
        coros = [fetch_and_save(session, url, output_path, **kwargs)
                 for url, output_path in url_and_output_path_pairs]
        return await asyncio.gather(*coros, loop)


def download_all(*url_and_output_path_pairs, loop=None, session=None,
                 **kwargs):
    """
    Save all given urls to the given files, asynchronously.

    :param url_and_output_path_pairs: An iterable of (url, output_path)
        pairs
    :param loop: the event loop. If None, get the current loop
    :param session: the ClientSession. If None, create a new session.
    :param kwargs: a dictionary of options passed to fetch_and_save
    """
    loop = loop or asyncio.get_event_loop()
    session = session or aiohttp.ClientSession(loop=loop)
    coros = [fetch_and_save(session, url, output_path, **kwargs)
             for url, output_path in url_and_output_path_pairs]

    res = loop.run_until_complete(asyncio.gather(*coros))
    loop.run_until_complete(session.close())
    return res
