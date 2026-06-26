#!/usr/bin/env python3
"""Firebase Hosting 배포 스크립트 — service account key 사용"""
import gzip, hashlib, json, mimetypes, os
from pathlib import Path
import requests

BASE = Path(__file__).parent
DIST = BASE / "dashboard" / "dist"
KEY_FILE = BASE / "engine" / "serviceAccountKey.json"
PROJECT_ID = "horizon-dc3c6"

def get_token():
    import google.oauth2.service_account as sa
    import google.auth.transport.requests as ga
    creds = sa.Credentials.from_service_account_file(
        str(KEY_FILE),
        scopes=["https://www.googleapis.com/auth/firebase.hosting"]
    )
    creds.refresh(ga.Request())
    return creds.token

def sha256gz(path):
    gz = gzip.compress(Path(path).read_bytes(), compresslevel=9)
    return hashlib.sha256(gz).hexdigest(), gz

def deploy():
    token = get_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    files = list(DIST.rglob("*"))
    files = [f for f in files if f.is_file()]
    print(f"파일 {len(files)}개 준비")

    file_map = {}
    gz_map = {}
    for f in files:
        rel = "/" + f.relative_to(DIST).as_posix()
        h, gz = sha256gz(f)
        file_map[rel] = h
        gz_map[h] = (gz, f)

    r = requests.post(
        f"https://firebasehosting.googleapis.com/v1beta1/sites/{PROJECT_ID}/versions",
        headers=headers,
        json={"config": {"rewrites": [{"glob": "**", "path": "/index.html"}]}}
    )
    r.raise_for_status()
    version = r.json()["name"]
    print(f"버전: {version}")

    r = requests.post(
        f"https://firebasehosting.googleapis.com/v1beta1/{version}:populateFiles",
        headers=headers,
        json={"files": file_map}
    )
    r.raise_for_status()
    needed = r.json().get("uploadRequiredHashes", [])
    print(f"업로드 필요: {len(needed)}개")

    upload_url = r.json()["uploadUrl"]
    for h in needed:
        gz_data, orig_file = gz_map[h]
        rr = requests.post(
            f"{upload_url}/{h}",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/octet-stream"},
            data=gz_data
        )
        rr.raise_for_status()
        print(f"  ✓ {orig_file.name}")

    r = requests.patch(
        f"https://firebasehosting.googleapis.com/v1beta1/{version}?updateMask=status",
        headers=headers,
        json={"status": "FINALIZED"}
    )
    r.raise_for_status()

    r = requests.post(
        f"https://firebasehosting.googleapis.com/v1beta1/sites/{PROJECT_ID}/releases?versionName={version}",
        headers=headers,
        json={}
    )
    r.raise_for_status()
    print(f"✅ 배포 완료! https://{PROJECT_ID}.web.app")

if __name__ == "__main__":
    deploy()
