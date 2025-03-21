import aiohttp.web
import aiohttp_jinja2
import jinja2


async def serve_index(request):
    return aiohttp_jinja2.render_template("index.html", request, {})


async def get_fund_info(request):
    fund_id = request.query.get('fund_id')

    if not fund_id:
        return aiohttp.web.json_response({"error": "Missing fund_id"}, status=400)

    fund_info = {
        "fund_id": fund_id,
        "name": "Sample Fund",
        "balance": 100000,
    }

    return aiohttp.web.json_response(fund_info)

app = aiohttp.web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('templates'))

app.add_routes([
    aiohttp.web.get("/", serve_index),
    aiohttp.web.get("/api/fund", get_fund_info)
])

app.add_routes([aiohttp.web.static("/static", './static')])

if __name__ == "__main__":
    aiohttp.web.run_app(app, host="127.0.0.1", port=8080)
