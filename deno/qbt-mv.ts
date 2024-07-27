
/*
	example:
	`deno run --allow-net=127.0.0.1:8780 --allow-read=/downloads --allow-write=/downloads mv.ts`

	this script is supposed to be ran on the same host
	I have no intention to support auth

	ref:
	https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)

	notes:
	the doc doesn't say specifically but it looks like:
		parameters are either:
			query string in GET
			x-www-form-urlencoded in POST
		response body can be plain text or JSON
*/

import * as path from 'jsr:@std/path';
import * as fs from 'jsr:@std/fs';

interface QBT {
	host: string;
	port: number;
}

const DONE_DIR = 'qbt-done';

function enc_params(p: Map<string, string>): string {
	const r: string[] = [];
	p.forEach((v, k) => { r.push(`${encodeURIComponent(k)}=${encodeURIComponent(v)}`); });
	return r.join('&');
}

async function call(qbt: QBT,
	http_method: 'GET' | 'POST',
	api: 'app' | 'torrents',
	method: string,
	parameters: Map<string, string> | null = null) {

	let url = `http://${qbt.host}:${qbt.port}/api/v2/${api}/${method}`;

	let resp;
	if (http_method == 'GET') {
		if (parameters != null) {
			url += '?' + enc_params(parameters);
		}
		// console.info(`URL: ${url}`);
		resp = await fetch(url, { method: 'GET' });
	} else if (http_method == 'POST') {
		if (parameters == null) {
			throw 'POST request without parameter';
		}
		const body = enc_params(parameters);
		// console.info(`URL: ${url}`);
		resp = await fetch(url, {
			method: 'POST',
			headers: {
				'content-type': 'application/x-www-form-urlencoded',
				'content-length': body.length.toString()
			},
			body
		});
	} else {
		// why do we have to write this, we've already exhausted 'GET' | 'POST'
		throw `${http_method} not supported`
	}

	// console.info(`${resp.status} ${resp.statusText}`);
	if (resp.status != 200) {
		throw `${resp.status} ${resp.statusText}`
	}
	/*
	resp.headers.forEach((v, k) => {
		console.info(`${k}: ${v}`);
	});
	*/

	if (resp.headers.get('content-type') == 'application/json') {
		return await resp.json();
	} else {
		return await resp.text();
	}
}

async function _version(qbt: QBT) {
	return await call(qbt, 'GET', 'app', 'version');
}

interface Torrent {
	state: string,
	hash: string,
	name: string,
	amount_left: number,
	content_path: string,
}

// https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#get-torrent-list
async function info(qbt: QBT, filter: string | null = null, sort: string | null = null): Promise<Torrent[]> {
	const p = new Map;
	if (filter !== null) {
		p.set('filter', filter);
	}
	if (sort !== null) {
		p.set('sort', sort);
	}
	return await call(qbt, 'GET', 'torrents', 'info', p);
}

// well delete is reserved in js
// https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)#delete-torrents
async function del(qbt: QBT, hashes: string[]) {
	return await call(qbt, 'POST', 'torrents', 'delete', new Map([['hashes', hashes.join('|')], ['deleteFiles', 'false']]));
}

async function mv_done(qbt: QBT) {
	// looks like filter 'paused' and state 'pausedUP' is what we are looking for
	const lst = await info(qbt, 'paused', 'added_on');
	// console.info(`${lst.length} entries`);
	const moved = [];
	for (const e of lst) {
		if (e.state !== 'pausedUP') {
			continue;
		}
		// console.info(`${e.state} ${e.amount_left} ${e.content_path}`);
		// we'll double check if it's complete by 'amount_left'
		if (e.amount_left > 0) {
			console.error(`${e.name} amount left is not 0, unexpected`);
			continue;
		}
		if (!fs.existsSync(e.content_path)) {
			console.error(`${e.content_path} doesn't exist, unexpected`);
			continue;
		}
		const new_path = path.join(path.dirname(e.content_path), '..', DONE_DIR, path.basename(e.content_path));
		// console.info(`\t-> ${new_path}`);
		if (fs.existsSync(new_path)) {
			console.error(`${new_path} already exists, will not move`);
			continue;
		}
		moved.push({
			hash: e.hash,
			name: e.name,
			path: e.content_path,
			new_path,
		});
	}
	if (moved.length > 0) {
		await del(qbt, moved.map(e => e.hash));
		console.info(`${moved.length} torrent(s) moved from qBittorrent:`)
		for (const e of moved) {
			console.info(e.name);
			try {
				fs.moveSync(e.path, e.new_path);
			} catch (e) {
				// some stupid group likes to use the same directory name for a series of releases
				// I'm not going to write a specific fix for their stupidity
				console.error(`error: ${e.toString()} while trying to move ${e.path}`);
			}	
		}
	}
}

if (import.meta.main) {
	const qbt = { host: '127.0.0.1', port: 8780 };
	// console.info(await version(qbt))
	await mv_done(qbt);
}
