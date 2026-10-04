"""Capture the site's term charts using its existing renderer."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread


def select_metrics(metrics: list[dict], query: str | None, agg: str | None) -> list[int]:
    candidates = [i for i, m in enumerate(metrics) if agg is None or m["agg"] == agg]
    if query is None:
        return candidates
    exact = [i for i in candidates if metrics[i]["metric"].casefold() == query.casefold()]
    matches = exact or [i for i in candidates if query.casefold() in metrics[i]["metric"].casefold()]
    if len(matches) != 1:
        choices = "\n".join(f'  {metrics[i]["metric"]} [{metrics[i]["agg"]}]' for i in matches)
        raise ValueError(f"Expected one metric, found {len(matches)}. Use --list and select --index, or narrow --metric/--agg.\n{choices}")
    return matches


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass


@contextmanager
def serve_site(directory: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(directory)))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def capture(site: Path, output: Path, metrics: list[dict], indices: list[int]) -> list[Path]:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    files = []
    with serve_site(site) as url, sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
            # Local captures must not silently fall back to a different online data release.
            context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(url) else route.abort())
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            page.wait_for_function("count => document.querySelectorAll('.metric-row').length === count", arg=len(metrics))
            page.evaluate("document.fonts.ready")
            styles = page.locator("style").all_text_contents()
            canvas = context.new_page()
            for index in indices:
                metric = metrics[index]
                if not metric.get("terms"):
                    raise ValueError(f'No term observations for {metric["metric"]}')
                row = page.locator(f'.metric-row[data-idx="{index}"]')
                row.locator('[data-col="metric"]').click()
                detail = page.locator(".detail-inner")
                detail.locator("svg").wait_for()
                # Reuse the rendered chart; remove the table's responsive metadata from the crop.
                markup = detail.evaluate("""element => {
                    const clone = element.cloneNode(true);
                    clone.querySelectorAll('.hidden-details').forEach(node => node.remove());
                    clone.querySelector('h3').textContent = clone.querySelector('h3').textContent.replaceAll('\u2014', '-');
                    return clone.outerHTML;
                }""")
                canvas.set_content("<html><head><style>" + "\n".join(styles) + """
                    body { padding: 0; background: #151515; }
                    .detail-inner { padding: 8px; width: max-content; overflow: visible; }
                    .detail-inner h3 { max-width: 675px; font-weight: 400; }
                    .detail-chart { margin: 0; }
                    </style></head><body>""" + markup + "</body></html>")
                canvas.evaluate("document.fonts.ready")
                name = re.sub(r"[^a-z0-9]+", "-", f'{metric["metric"]}-{metric["agg"]}'.lower()).strip("-")
                path = output / f"{index + 1:03d}-{name}.png"
                canvas.locator(".detail-inner").screenshot(path=str(path), animations="disabled")
                files.append(path)
                print(path)
        finally:
            browser.close()
    return files


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--metric", help="Metric name, or an unambiguous part of it.")
    choice.add_argument("--index", type=int, help="One-based row number from --list.")
    choice.add_argument("--all", action="store_true", help="Capture every metric.")
    choice.add_argument("--list", action="store_true", help="List metric names and aggregation kinds.")
    parser.add_argument("--agg", help="Aggregation kind to disambiguate matching metric names.")
    parser.add_argument("--site", type=Path, default=Path("site"), help="Site directory (default: site).")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/screenshots"))
    args = parser.parse_args()
    metrics = json.loads((args.site / "data.json").read_text())["metrics"]
    if args.list:
        for index, metric in enumerate(metrics, 1):
            print(f'{index}: {metric["metric"]} [{metric["agg"]}]')
        return
    try:
        if args.index is not None:
            if not 1 <= args.index <= len(metrics):
                raise ValueError(f"--index must be between 1 and {len(metrics)}")
            if args.agg:
                raise ValueError("Use --index alone, without --agg")
            indices = [args.index - 1]
        else:
            indices = select_metrics(metrics, args.metric, args.agg)
        if not indices:
            raise ValueError("No metrics match the requested aggregation.")
        capture(args.site.resolve(), args.output_dir, metrics, indices)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
