from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="Единый CLI для DataFrame")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("index", help="Собрать индекс (чанки -> эмбеддинги -> Qdrant/PG)")
    sub.add_parser("chat", help="Запустить интерактивный RAG-чат")
    sub.add_parser("init-db", help="Создать схему PostgreSQL")
    sub.add_parser("convert-guide", help="Конвертировать путеводитель Excel -> knowledge_base.*")

    upload = sub.add_parser("upload-source", help="Загрузить файл в source_documents и (опционально) переиндексировать")
    upload.add_argument("file")
    upload.add_argument("--name", type=str, default=None)
    upload.add_argument("--init-schema", action="store_true")
    upload.add_argument("--no-index", action="store_true")

    args = parser.parse_args()

    if args.command == "index":
        from .rag.ingest_pipeline import main as build_index_main

        build_index_main()
    elif args.command == "chat":
        from .dialog.interactive import main as chat_main

        chat_main()
    elif args.command == "init-db":
        from .scripts.init_db import main as init_db_main

        init_db_main()
    elif args.command == "convert-guide":
        from .ingestion.convert_guide.convert_guide import main as convert_guide_main

        convert_guide_main()
    elif args.command == "upload-source":
        from .scripts.upload_source import main as upload_source_main

        upload_source_main(
            argv=[
                args.file,
                *(["--name", args.name] if args.name else []),
                *(["--init-schema"] if args.init_schema else []),
                *(["--no-index"] if args.no_index else []),
            ]
        )

