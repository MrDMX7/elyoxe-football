"""Deploys the desk (Phase 2b): the SSM key (made once), the Lambda's role, the Lambda tifo-desk and its HTTP API (ap-south-1;
a Function URL returns 403 in this account). Idempotent: run it again after any change to desk/lambda/ or publish.py.
Prints the owner's link, with the key in the fragment. The key is never written to the repo.

  python desk/deploy.py            deploy and print the link
  python desk/deploy.py --link     only print the link"""
import io, json, secrets, shutil, subprocess, sys, tempfile, time, zipfile
from pathlib import Path
import boto3

REGION, NAME, PARAM = "ap-south-1", "tifo-desk", "/tifo/desk-key"
BUCKET = "elyoxe-football-574771023173-ap-south-1"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def desk_key(ssm):
    try:
        return ssm.get_parameter(Name=PARAM, WithDecryption=True)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        k = secrets.token_urlsafe(32)
        ssm.put_parameter(Name=PARAM, Value=k, Type="SecureString", Description="Tifo desk key (desk/deploy.py)")
        return k


def role(iam, account):
    trust = {"Version": "2012-10-17", "Statement": [{"Effect": "Allow", "Principal": {"Service": "lambda.amazonaws.com"}, "Action": "sts:AssumeRole"}]}
    try:
        arn, fresh = iam.get_role(RoleName=NAME)["Role"]["Arn"], False
    except iam.exceptions.NoSuchEntityException:
        arn, fresh = iam.create_role(RoleName=NAME, AssumeRolePolicyDocument=json.dumps(trust))["Role"]["Arn"], True
    iam.attach_role_policy(RoleName=NAME, PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole")
    b = f"arn:aws:s3:::{BUCKET}"
    policy = {"Version": "2012-10-17", "Statement": [
        {"Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject"], "Resource": [f"{b}/state/articles/*", f"{b}/v1/news/*"]},
        {"Effect": "Allow", "Action": "s3:ListBucket", "Resource": b, "Condition": {"StringLike": {"s3:prefix": ["state/articles/versions/*"]}}},
        {"Effect": "Allow", "Action": "ssm:GetParameter", "Resource": f"arn:aws:ssm:{REGION}:{account}:parameter{PARAM}"}]}
    iam.put_role_policy(RoleName=NAME, PolicyName="desk", PolicyDocument=json.dumps(policy))
    if fresh:
        time.sleep(12)                                   # a new role takes a few seconds before Lambda can assume it
    return arn


def bundle():
    tmp = Path(tempfile.mkdtemp())
    for f in ("app.py", "s3store.py", "desk.html"):
        shutil.copy(HERE / "lambda" / f, tmp / f)
    shutil.copy(ROOT / "news" / "articles" / "publish.py", tmp / "publish.py")
    subprocess.run([sys.executable, "-m", "pip", "install", "pillow", "--platform", "manylinux2014_x86_64", "--only-binary=:all:",
                    "--python-version", "3.13", "--implementation", "cp", "--no-deps", "--target", str(tmp), "-q"], check=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in tmp.rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                z.write(p, p.relative_to(tmp).as_posix())
    shutil.rmtree(tmp, ignore_errors=True)
    return buf.getvalue()


def function(lam, role_arn, code):
    env = {"Variables": {"BUCKET": BUCKET, "KEY_PARAM": PARAM}}
    try:
        lam.get_function(FunctionName=NAME)
        lam.update_function_code(FunctionName=NAME, ZipFile=code)
        lam.get_waiter("function_updated_v2").wait(FunctionName=NAME)
        lam.update_function_configuration(FunctionName=NAME, Role=role_arn, Timeout=30, MemorySize=512, Environment=env)
        lam.get_waiter("function_updated_v2").wait(FunctionName=NAME)
    except lam.exceptions.ResourceNotFoundException:
        lam.create_function(FunctionName=NAME, Runtime="python3.13", Handler="app.handler", Role=role_arn, Code={"ZipFile": code},
                            Architectures=["x86_64"], Timeout=30, MemorySize=512, Environment=env,
                            Description="Tifo desk: the news queue, published articles, editing (saas/football/desk)")
        lam.get_waiter("function_active_v2").wait(FunctionName=NAME)
    return lam.get_function(FunctionName=NAME)["Configuration"]["FunctionArn"]


def api(gw, lam, fn_arn, account):
    found = next((a for a in gw.get_apis(MaxResults="100").get("Items", []) if a["Name"] == NAME), None)
    if not found:
        found = gw.create_api(Name=NAME, ProtocolType="HTTP", Target=fn_arn)      # $default route and an auto-deployed stage
    try:
        lam.add_permission(FunctionName=NAME, StatementId="desk-api", Action="lambda:InvokeFunction", Principal="apigateway.amazonaws.com",
                           SourceArn=f"arn:aws:execute-api:{REGION}:{account}:{found['ApiId']}/*")
    except lam.exceptions.ResourceConflictException:
        pass
    return found["ApiEndpoint"]


def main(argv):
    s = boto3.Session(region_name=REGION)
    account = s.client("sts").get_caller_identity()["Account"]
    ssm, lam, gw = s.client("ssm"), s.client("lambda"), s.client("apigatewayv2")
    k = desk_key(ssm)
    if "--link" not in argv:
        arn = function(lam, role(s.client("iam"), account), bundle())
        end = api(gw, lam, arn, account)
    else:
        end = next(a["ApiEndpoint"] for a in gw.get_apis(MaxResults="100")["Items"] if a["Name"] == NAME)
    print(f"{end}/#k={k}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
