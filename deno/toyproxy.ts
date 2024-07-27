// `deno run --allow-net toyproxy.ts`

import * as radio from "./radio_cn.ts";

function txt_resp(status: number, body: BodyInit): Response {
	return new Response(body, {
		status,
		headers: {
			'content-type': 'text/plain; charset=utf-8',
		}
	});
}

function not_found(): Response {
	return txt_resp(404, "you're (not) welcome");
}

function redirect(location: string, status: number = 302): Response {
	return new Response(null, { status, headers: { location } });
}

function prechk(path: string, pre: string) {
	return path.slice(0, pre.length) === pre;
}

// so we can use shortened urls like http://127.0.0.1:8080/r/nhkr1
const REDIRECTS = new Map([
	["nhkr1", "/p/radio-stream.nhk.jp/hls/live/2023229/nhkradiruakr1/master48k.m3u8"],
	["nhkr2", "/p/radio-stream.nhk.jp/hls/live/2023501/nhkradiruakr2/master48k.m3u8"],
	["nhkfm", "/p/radio-stream.nhk.jp/hls/live/2023507/nhkradiruakfm/master48k.m3u8"],
]);

async function handle(req: Request, info: Deno.ServeHandlerInfo) {
	const url = new URL(req.url);
	console.log(`${info.remoteAddr.hostname}:${info.remoteAddr.port} ${decodeURI(url.pathname)}`)

	if (url.pathname == '/' || url.pathname == '/trace') {
		return txt_resp(200, `Deno: ${Deno.version.deno}
remoteAddr: ${info.remoteAddr.hostname}
=== headers ===
${Array.from(req.headers.entries()).map(e => `${e[0]}: ${e[1]}`).join('\n')}
`);
	} else if (prechk(url.pathname, '/r/')) {
		const loc = REDIRECTS.get(url.pathname.slice(3));
		if (loc === undefined) {
			console.log(`\t-> 404`);
			return not_found();
		}
		console.log(`\t-> ${loc}`);
		return redirect(loc);
	} else if (prechk(url.pathname, '/p/')) {
		const origin = `https://${url.pathname.slice(3)}`;
		console.log(`\t-> ${origin}`);

		const headers = Array.from(req.headers.entries());
		headers.push(['x-forwarded-for', '1.72.50.1']);

		return await fetch(origin, {
			method: req.method,
			headers,
			body: req.body,
		})
	} else if (prechk(url.pathname, '/radio.cn/')) {
		const m = /^(\d+)-(\d+)-(\d+)/.exec(url.pathname.slice(10));
		if (m == null) {
			return not_found();
		}
		const loc = await radio.get(parseInt(m[1]), parseInt(m[2]), parseInt(m[3]));
		if (loc === null) {
			return not_found();
		}
		return redirect(loc);
	} else {
		return not_found();
	}
}

if (import.meta.main) {
	const args = Deno.args;
	let hostname, port;
	if (args.length > 0) {
		hostname = args[0];
	} else {
		hostname = '127.0.0.1';
	}
	if (args.length > 1) {
		port = parseInt(args[1]);
	} else {
		port = 8080;
	}
	Deno.serve({ hostname, port }, handle);
}
