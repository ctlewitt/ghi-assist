from bottle import request, post, run, abort, Bottle
import json
from os.path import normpath, dirname, abspath, join
from ghi_assist.utils import byteify
from ghi_assist.webhook import Webhook
from ghi_assist.hooks import AssignRelatedHook, ClaimHook, CommentLabelHook, NewIssueLabelHook, \
    NewPrLabelHook, PingHook, AssignedLabelHook, UrlLabelHook

app = Bottle()
path = normpath(abspath(dirname(__file__)))
with open(join(path, '../etc', 'config.json')) as config_file:
    app.config.load_dict(byteify(json.load(config_file)))
app.config.setdefault('server.host', 'localhost')
app.config.setdefault('server.port', '8080')

webhook = Webhook(secret=app.config.get("github.secret"), api_token=app.config.get("github.api_token"))

if app.config.get("labels.autoload"):
    labels = webhook.load_repo_labels(app.config.get("github.repository"))
else:
    labels = app.config.get("labels.whitelist")

webhook.register("ping", PingHook())
webhook.register("issue_comment", CommentLabelHook(
    whitelist=labels,
    aliases=app.config.get("labels.aliases")[0] # hidden in an array to prevent the nesting from being used
                                            # as namespace by load_dict
))
webhook.register("issue_comment", ClaimHook())
webhook.register("issue_comment", UrlLabelHook(r"https?://www\.dreamwidth\.org/support/see_request\?id=\d+", ["from: support"]))
webhook.register("issues", UrlLabelHook(r"https?://www\.dreamwidth\.org/support/see_request\?id=\d+", ["from: support"]))
webhook.register("issues", NewIssueLabelHook(
    whitelist=labels,
    aliases=app.config.get("labels.aliases")[0]
))
webhook.register("issues", AssignedLabelHook())
webhook.register("pull_request", NewPrLabelHook(
    whitelist=labels,
    aliases=app.config.get("labels.aliases")[0]
))
webhook.register("pull_request", AssignRelatedHook())

@post('/')
def github_webhook():
    """
    Main app entrypoint.
    """
    signature_header = request.headers.get('X-Hub-Signature')
    if signature_header is None:
        abort(403, "No X-Hub-Signature header.")

    digest_mode, signature = signature_header.split('=')
    if digest_mode != "sha1":
        abort(501, "'%s' not supported." % digest_mode)
    if not webhook.signature_valid(data=request.body.read(), signed_data=signature):
        abort(403, "Signature does not match expected value.")

    event = request.headers.get('X-GitHub-Event')
    responses = webhook.respond_to(event, request.json)
    pretty_responses = "\n".join([json.dumps(s, indent=4) for s in responses])
    return "Responded to %s.\n%s" % (event, pretty_responses)

run(host=app.config.get('server.host'), port=app.config.get('server.port'))