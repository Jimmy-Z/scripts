// example: `deno run --allow-env=XDG_CONFIG_HOME,HOME --allow-read=$HOME/.config/slack_webhook --allow-net slack.ts 'Hello slack'`

import * as path from 'jsr:@std/path';
import config_dir from 'https://deno.land/x/dir/config_dir/mod.ts';

export function get_webhook_url() {
	const conf_dir = config_dir();
	if (conf_dir === null) {
		throw 'not expected';
	}
	return Deno.readTextFileSync(path.join(conf_dir, 'slack_webhook')).trim();
}

export async function post(url: string, text: string) {
	text = text.trim();
	if (text.length == 0) {
		return;
	}
	const resp = await fetch(url, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/JSON',
		},
		body: JSON.stringify({ text })
	});
	console.info(`${resp.status} ${resp.statusText}`);
	console.info(await resp.text())
}

if (import.meta.main) {
	const args = Deno.args;
	if (args.length > 0 ) {
		// text as command line args
		await post(get_webhook_url(), args.join(' '));
	}else {
		// text from stdin
		const text = [];
		const d = new TextDecoder();
		for await(const c of Deno.stdin.readable) {
			text.push(d.decode(c));
		}
		await post(get_webhook_url(), text.join(''));
	}
}
