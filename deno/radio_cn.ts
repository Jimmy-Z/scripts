// radio.cn handling
// https://www.radio.cn/pc-portal/js/api.js?061

// web crypto doesn't support md5
import { crypto } from "jsr:@std/crypto/crypto";

const MODULE = "radio.cn";

const key = 'f0fc4c668392f9f9a447e48584c214ee';

async function md5(msg: string) {
	return Array.from(new Uint8Array(await crypto.subtle.digest('MD5', new TextEncoder().encode(msg))),
		(b) => b.toString(16).padStart(2, '0')).join('');
}

/*
	categoryId:
		0 all
		5 music
		15 traffic
	provinceCode:
		0 national
		330000 Zhejiang
		420000 Hubei
*/
export async function list(provinceCode: number, categoryId: number) {
	const url = `https://ytmsout.radio.cn/web/appBroadcast/list?categoryId=${categoryId}&provinceCode=${provinceCode}`;
	const ts = new Date().getTime().toString();
	const sign = await md5(`categoryId=${categoryId}&provinceCode=${provinceCode}&timestamp=${ts}&key=${key}`);
	const resp = await fetch(url, {
		headers: {
			'Content-Type': 'application/json',
			Timestamp: ts,
			Sign: sign,
			Platformcode: 'WEB',
			Equipmentid: '0',
		}
	});
	console.log(`${MODULE} ${resp.status} ${resp.statusText} ${url}`);
	if (resp.status == 200) {
		return await resp.json();
	} else {
		return null;
	}
}

interface List {
	code: number,
	message: string,
	data: Array<Content>,
};

interface Content {
	contentId: string,
	title: string,
	subtitle: string,
	playUrlLow: string,
	mp3PlayUrlLow: string,
	mp3PlayUrlHigh: string,
	playUrlMulti: string,
};

function c2str(c: Content) {
	return `${c.title} - ${c.subtitle}`;
}

function best(c: Content) {
	return c.playUrlMulti || c.mp3PlayUrlHigh || c.playUrlLow || c.mp3PlayUrlLow;
}

const cache: Map<number, [number, Content]> = new Map;

function prune(ts: number) {
	let c = 1;
	Array.from(cache.entries()).forEach(e => {
		if (e[1][0] == ts) {
			cache.delete(e[0]);
			c += 1;
		}
	});
	console.log(`${MODULE} ${c} entries pruned from cache`);
}

export async function get(contentId: number, provinceCode: number, categoryId: number): Promise<string | null> {
	// console.log(`contentId: ${contentId}`);
	let c = cache.get(contentId);
	if (c !== undefined) {
		console.log(`${MODULE} cache hit ${c2str(c[1])}`);
		return best(c[1]);
	}
	const ts = Date.now();
	const lst: List | null = await list(provinceCode, categoryId);
	if (lst === null) {
		console.error(`${MODULE} failed to retrieve list`);
		return null;
	}
	console.log(`${MODULE} ${lst.code} ${lst.message}`);
	if (lst.code !== 0) {
		console.error(`${MODULE} failed to retrieve list`);
		return null;
	}
	for (const c of lst.data) {
		const id = parseInt(c.contentId);
		console.log(`${MODULE} ${c.contentId} ${c2str(c)}`);
		cache.set(id, [ts, c]);
	}
	setTimeout(() => { prune(ts); }, 300000);
	c = cache.get(contentId);
	if (c !== undefined) {
		console.log(`${MODULE} ${c[1].contentId} ${c2str(c[1])}`);
		return best(c[1]);
	}
	return null;
}

function pretty_lst(lst: List) {
	for (const c of lst.data) {
		console.log(`${MODULE} ${c.contentId} ${c2str(c)} ${best(c)}`);
	}
}

if (import.meta.main) {
	const args = Deno.args;
	if (args.length == 0) {
		pretty_lst(await list(0, 0));
	} else if (args[0] == "list") {
		pretty_lst(await list(
			args.length >= 2 ? parseInt(args[1]) : 0,
			args.length >= 3 ? parseInt(args[2]) : 0
		));
	} else if (args[0] == "get") {
		console.log(await get(
			args.length >= 2 ? parseInt(args[1]) : 0,
			args.length >= 3 ? parseInt(args[2]) : 0,
			args.length >= 4 ? parseInt(args[3]) : 0
		));
	}
}
