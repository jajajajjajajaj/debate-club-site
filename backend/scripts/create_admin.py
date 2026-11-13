"""첫 관리자 계정 만들기.

사용법 (backend 폴더에서, .env 설정 후):
    python -m scripts.create_admin --name 홍길동 --student-id 20201234 --password '충분히-긴-비밀번호'

이미 있는 학번이면 새로 만들지 않고 권한만 admin 으로 올립니다.
"""
import argparse
import sys

from app.db import get_supabase
from app.routers.members import member_email


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--student-id", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--major", default="")
    parser.add_argument("--generation", default="")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("비밀번호는 8자 이상이어야 합니다.")
        return 1

    sb = get_supabase()
    existing = sb.table("users").select("id").eq("student_id", args.student_id).limit(1).execute()
    if existing.data:
        sb.table("users").update({"role": "admin"}).eq("id", existing.data[0]["id"]).execute()
        print("이미 있는 회원입니다. 관리자 권한으로 변경했습니다. (비밀번호는 그대로)")
        return 0

    email = member_email(args.student_id)
    created = sb.auth.admin.create_user({"email": email, "password": args.password, "email_confirm": True})
    user_id = created.user.id
    sb.table("users").insert(
        {
            "id": user_id,
            "email": email,
            "name": args.name,
            "student_id": args.student_id,
            "major": args.major,
            "generation": args.generation,
            "role": "admin",
            "must_change_password": False,
        }
    ).execute()
    print(f"관리자 계정을 만들었습니다: {args.name} ({args.student_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
