import argparse
import os
import logging
import aiofiles
import asyncio
from aiohttp import web
from asyncio import subprocess

logger = logging.getLogger(__name__)

CHUNK_SIZE = 100*1024


async def create_archiving_process(dir_path):
    process = await subprocess.create_subprocess_exec(
        'zip', '-r', '-', '.',
        cwd=dir_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    return process


async def archive_handler(request):
    dir_name = request.match_info['archive_hash']
    dir_path = os.path.join(app['working_dir'], dir_name)
    if not os.path.exists(dir_path):
        logger.warning(f'Cannot access {dir_path}: No such directory')
        raise web.HTTPNotFound(text='Архив удален или перемещен')
    logger.info(f'Started sending the archive {dir_name}.zip')
    process = await create_archiving_process(dir_path)

    response = web.StreamResponse()

    response.headers['Content-Type'] = 'multipart/form-data;'
    response.headers['Content-Disposition'] = f'attachment; filename="{dir_name}.zip"'

    await response.prepare(request)

    try:
        while not process.stdout.at_eof():
            archive_chunk = await process.stdout.read(CHUNK_SIZE)
            logger.info(f'Sending archive chunk {len(archive_chunk)} bytes to length')
            await response.write(archive_chunk)
            await asyncio.sleep(app['latency'])
    except asyncio.CancelledError:
        logger.info('Download was interrupted')
        raise
    except SystemExit:
        logger.error('System Exit exception')
    else:
        if not process.returncode == 0:
            logger.warning(f'Received eof, but zip process return code is {process.returncode}')
            raise web.HTTPServerError()
        logger.debug('Zip process exit status is OK')
        await response.write_eof()
        logger.info('Archive has been sent')
        return response
    finally:
        if process.returncode is None:
            logger.debug("Killing zip process")
            process.kill()
            await process.comunicate()
            raise web.HTTPBadRequest(text='Abort connection')


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='ProgramName',
        description='What the program does',
        epilog='Text at the bottom of help',
    )
    parser.add_argument(
        '-l', '--log',
        dest='logLevel',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        help='Set the logging level',
        default='INFO',
    )
    parser.add_argument('-d', '--directory', type=str, default='test_photos', help='photos directory')
    parser.add_argument('-lat', '--latency', type=float, default=0.2, help='stream response delay')
    args = parser.parse_args()

    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=getattr(logging, args.logLevel),
    )

    app = web.Application()
    app['latency'] = args.latency
    app['working_dir'] = args.directory
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive_handler),
    ])
    web.run_app(app)
