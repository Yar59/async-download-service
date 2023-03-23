import os

import aiofiles
import asyncio
import datetime
from aiohttp import web
from asyncio import subprocess

INTERVAL_SECS = 1


async def create_archive(dir_path):
    process = await subprocess.create_subprocess_exec(
        "zip", "-j", "-r", "-", dir_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return process


async def archive_handler(request):
    dir_name = request.match_info.get('archive_hash')
    dir_path = os.path.join('test_photos', dir_name)
    if not os.path.exists(dir_path):
        raise web.HTTPNotFound()
    process = await create_archive(dir_path)

    response = web.StreamResponse()

    response.headers['Content-Type'] = 'multipart/form-data;'
    response.headers['Content-Disposition'] = f'attachment; filename="{dir_name}.zip"'

    await response.prepare(request)

    while True:

        await response.write(await process.stdout.read(102400))

        if process.stdout.at_eof():
            break
    return response


async def archive(request):
    raise NotImplementedError


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    app = web.Application()
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive_handler),
    ])
    web.run_app(app)
