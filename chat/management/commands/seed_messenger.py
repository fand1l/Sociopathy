import random
import string
from datetime import timedelta
import urllib.error
import urllib.request

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from accounts.models import Profile
from bookmarks.models import Bookmark
from chat.models import (
    ChatGroup,
    ChatGroupMembership,
    ChatGroupMessage,
    ChatMessage,
    ChatThread,
    ChatThreadNotificationSetting,
)
from likes.models import Like
from posts.models import Post
from relationships.models import Follow


BIO_OPTIONS = [
    "Люблю каву, меми і довгі переписки вночі.",
    "Онлайн майже завжди, якщо не сплю 😴",
    "Пишу швидко, друкую повільно.",
    "Тут для нових знайомств і цікавих розмов.",
    "Днем працюю, ввечері живу в чатах.",
    "Можу зникнути на годину і повернутись з 20 повідомленнями.",
    "Вчу Django, страждаю від міграцій. 🐍",
    "Студент Політехніки. Шукаю де випити кави між парами. ☕",
    "Живу на Fedora, граю в Minecraft, пишу код. 🐧",
    "Backend developer у душі, UI/UX дизайнер у кошмарах.",
]

POST_TEXTS = [
    "Сьогодні продуктивний день. Закрив(-ла) одразу кілька задач ✅",
    "Щойно викотив(-ла) оновлення, буду вдячний(-а) за фідбек.",
    "Іноді найкраще рішення — найпростіше.",
    "Потрібна порада: як би ви спроєктували це API?",
    "Маленький прогрес щодня = великий результат з часом.",
    "Піймав(-ла) баг, який ховався тиждень. Перемога!",
    "Хто за невеликий networking у коментарях?",
    "Ділюсь думкою дня: дисципліна перемагає мотивацію.",
    "У кого є хороший плейлист для фокусної роботи?",
    "Сьогодні тестую новий підхід — поки виглядає багатообіцяюче.",
]

COMMENT_TEXTS = [
    "Підтримую, хороша думка.",
    "Цікаво, дякую за шеринг.",
    "Згоден(-на), але є ще один варіант.",
    "Спробуй ще подивитися в бік кешування.",
    "Теж стикався(-лась) з цим, вирішив(-ла) трохи інакше.",
    "Класно написано 👏",
    "Можеш уточнити, який саме кейс?",
]

PRIVATE_MESSAGES = [
    "Привіт! Як настрій сьогодні?",
    "Ти бачив(-ла), що в стрічці щойно опублікували?",
    "Я зараз в дорозі, відповім трохи пізніше.",
    "Давай після обіду обговоримо це детальніше.",
    "Скинь, будь ласка, посилання ще раз 🙏",
    "Класна ідея, мені подобається.",
    "Я трохи випав з контексту, нагадай останній крок.",
    "Ок, домовились ✅",
    "Гаразд, беру це на себе.",
    "Супер, тоді рухаємось далі.",
]

GROUP_MESSAGES = [
    "Всім привіт 👋",
    "Хто сьогодні на зв'язку?",
    "Давайте синхронізуємось по плану на день.",
    "Потрібно 2 людини на швидкий review.",
    "Хто може підхопити задачу до вечора?",
    "Оновив(-ла) статус, можна перевіряти.",
    "Дякую всім за оперативність 🙌",
    "Є ідея, але треба обговорити нюанси.",
    "Можемо зробити короткий кол завтра?",
    "Наче все зійшлось, перевірте ще раз.",
]

GROUP_NAME_PREFIXES = [
    "Команда", "Тусовка", "Флудилка", "Нічний чат", "Денний канал", "Кімната", "Проєкт", "Лабораторія",
]
GROUP_NAME_SUFFIXES = [
    "Alpha", "Beta", "Kyiv", "Pulse", "Orbit", "Wave", "Crew", "Devs", "Squad", "Nexus", "Flow",
]

FIRST_NAMES = [
    "Artem", "Maksym", "Nazar", "Sofia", "Olena", "Kateryna", "Iryna", "Andrii", "Mykola", "Roman",
    "Yulia", "Daria", "Alina", "Bohdan", "Denys", "Vladyslav", "Anastasia", "Polina", "Oleksii",
    "Yaroslav", "Maria", "Veronika", "Pavlo", "Taras",
]
LAST_NAMES = [
    "Bondar", "Shevchenko", "Kovalenko", "Tkachenko", "Kravets", "Polishchuk", "Melnyk", "Boyko", "Koval",
    "Tymoshenko", "Marchenko", "Havryliuk", "Lysenko", "Petryk", "Lytvyn", "Novak", "Shapoval",
    "Symonenko", "Rudenko", "Mazur", "Hrytsenko", "Ivanenko", "Sydorenko", "Kushnir",
]

SHARE_TEXT_PREFIX = "Поділився постом:"


class Command(BaseCommand):
    help = "Повне заповнення соцмережі і месенджера ботами, контентом та активністю."

    def add_arguments(self, parser):
        parser.add_argument("--wipe-db", action="store_true", help="Повністю очистити БД перед генерацією (flush).")
        parser.add_argument("--dry-run", action="store_true", help="Прогнати генерацію без збереження змін.")
        parser.add_argument("--seed", type=int, default=None, help="Фіксований seed random для повторюваності.")
        parser.add_argument("--batch-size", type=int, default=500, help="batch_size для bulk_create.")

        parser.add_argument("--users", type=int, default=120, help="Кількість бот-акаунтів.")
        parser.add_argument("--bot-password", type=str, default="crowd12345", help="Пароль для ботів.")

        parser.add_argument("--threads", type=int, default=260, help="Кількість приватних тредів.")
        parser.add_argument("--groups", type=int, default=40, help="Кількість групових чатів.")
        parser.add_argument("--private-msg-min", type=int, default=15)
        parser.add_argument("--private-msg-max", type=int, default=70)
        parser.add_argument("--group-msg-min", type=int, default=25)
        parser.add_argument("--group-msg-max", type=int, default=120)

        parser.add_argument("--posts", type=int, default=320, help="Кількість постів.")
        parser.add_argument("--comments-min", type=int, default=1)
        parser.add_argument("--comments-max", type=int, default=6)
        parser.add_argument("--likes-max", type=int, default=30)
        parser.add_argument("--repost-ratio", type=float, default=0.22)
        parser.add_argument("--share-count", type=int, default=260, help="Скільки разів поділитися постами у чати.")

        parser.add_argument("--days-back", type=int, default=45, help="Глибина випадкових дат у минуле.")
        parser.add_argument(
            "--progress-every",
            type=int,
            default=25,
            help="Як часто показувати прогрес у довгих циклах.",
        )

    def handle(self, *args, **options):
        self._validate_options(options)

        if options["seed"] is not None:
            random.seed(options["seed"])

        self._image_cache = {}
        self._progress_every = options["progress_every"]

        if options["wipe_db"]:
            self.stdout.write(self.style.WARNING("Flushing database..."))
            call_command("flush", verbosity=0, interactive=False)
            self.stdout.write(self.style.SUCCESS("Database flushed."))

        with transaction.atomic():
            stats = self._seed_all(options)
            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "DRY-RUN" if options["dry_run"] else "DONE"
        self.stdout.write(self.style.SUCCESS(f"[{mode}] Seed finished."))
        for key, value in stats.items():
            self.stdout.write(f"{key}: {value}")

        self.stdout.write(
            self.style.WARNING(
                "Note: group chat model має лише text, тому 'картинки в групі' реалізовані через шер post-ів з прев'ю зображення."
            )
        )

    def _validate_options(self, options):
        int_fields = [
            "users", "threads", "groups", "private_msg_min", "private_msg_max", "group_msg_min", "group_msg_max",
            "posts", "comments_min", "comments_max", "likes_max", "share_count", "days_back", "batch_size",
        ]
        for field in int_fields:
            if options[field] < 0:
                raise CommandError(f"--{field.replace('_', '-')} не може бути менше 0")

        if options["users"] < 2:
            raise CommandError("--users має бути не менше 2")
        if options["private_msg_min"] > options["private_msg_max"]:
            raise CommandError("--private-msg-min не може бути більшим за --private-msg-max")
        if options["group_msg_min"] > options["group_msg_max"]:
            raise CommandError("--group-msg-min не може бути більшим за --group-msg-max")
        if options["comments_min"] > options["comments_max"]:
            raise CommandError("--comments-min не може бути більшим за --comments-max")
        if not 0 <= options["repost_ratio"] <= 1:
            raise CommandError("--repost-ratio має бути в межах 0..1")
        if options["days_back"] < 1:
            raise CommandError("--days-back має бути не менше 1")
        if options["batch_size"] < 1:
            raise CommandError("--batch-size має бути не менше 1")
        if options["progress_every"] < 1:
            raise CommandError("--progress-every має бути не менше 1")

    def _seed_all(self, options):
        self.stdout.write("[1/8] Створення бот-акаунтів...")
        users = self._create_bot_users(
            target_users=options["users"],
            bot_password=options["bot_password"],
        )

        self.stdout.write("[2/8] Побудова соціального графа (follow)...")
        follows_created = self._seed_follows(users, options["batch_size"])
        self.stdout.write("[3/8] Створення постів...")
        posts = self._seed_posts(users, options["posts"], options["days_back"])
        self.stdout.write("[4/8] Генерація коментарів...")
        comments_created = self._seed_comments(
            users,
            posts,
            options["comments_min"],
            options["comments_max"],
            options["days_back"],
            options["batch_size"],
        )
        self.stdout.write("[5/8] Лайки, закладки та репости...")
        likes_created, bookmarks_created = self._seed_likes_and_bookmarks(
            users,
            posts,
            options["likes_max"],
            options["batch_size"],
        )
        reposts_created = self._seed_reposts(users, posts, options["repost_ratio"], options["days_back"])

        self.stdout.write("[6/8] Приватні чати й повідомлення...")
        private_messages_created, threads_created = self._seed_private_threads(
            users=users,
            target_threads=options["threads"],
            min_messages=options["private_msg_min"],
            max_messages=options["private_msg_max"],
            days_back=options["days_back"],
            batch_size=options["batch_size"],
            posts=posts,
        )

        self.stdout.write("[7/8] Групи й групові повідомлення...")
        group_messages_created, groups_created = self._seed_groups(
            users=users,
            target_groups=options["groups"],
            min_messages=options["group_msg_min"],
            max_messages=options["group_msg_max"],
            days_back=options["days_back"],
            batch_size=options["batch_size"],
            posts=posts,
        )

        self.stdout.write("[8/8] Додаткові шери постів у чати...")
        shares_created = self._seed_extra_shares(users, posts, options["share_count"], options["days_back"])

        return {
            "users_total": len(users),
            "posts_created": len(posts),
            "comments_created": comments_created,
            "reposts_created": reposts_created,
            "likes_created": likes_created,
            "bookmarks_created": bookmarks_created,
            "follows_created": follows_created,
            "threads_total": self._private_thread_queryset().count(),
            "threads_created": threads_created,
            "private_messages_created": private_messages_created,
            "groups_total": ChatGroup.objects.count(),
            "groups_created": groups_created,
            "group_messages_created": group_messages_created,
            "shares_created": shares_created,
        }

    def _create_bot_users(self, target_users, bot_password):
        User = get_user_model()
        users = []
        existing_usernames = set(
            User.objects.values_list("username", flat=True)
        )

        while len(users) < target_users:
            first_name, last_name, username = self._build_random_identity(existing_usernames)
            existing_usernames.add(username)

            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.test",
                password=bot_password,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
            )
            self._ensure_profile(user)
            users.append(user)
            self._progress(len(users), target_users, "Боти")

        return users

    def _seed_follows(self, users, batch_size):
        profiles = list(Profile.objects.filter(user__in=users))
        follows = []
        seen = set()

        for profile in profiles:
            candidates = [p for p in profiles if p.id != profile.id]
            if not candidates:
                continue
            follow_target_count = random.randint(3, min(18, len(candidates)))
            for target in random.sample(candidates, follow_target_count):
                key = (profile.id, target.id)
                if key in seen:
                    continue
                seen.add(key)
                follows.append(Follow(user_from=profile, user_to=target))

        if follows:
            Follow.objects.bulk_create(follows, batch_size=batch_size, ignore_conflicts=True)
        return len(follows)

    def _seed_posts(self, users, target_posts, days_back):
        posts = []
        for idx in range(target_posts):
            author = random.choice(users)
            post = Post.objects.create(author=author, content=random.choice(POST_TEXTS))

            created_at = self._random_start_time(days_back)
            Post.objects.filter(pk=post.id).update(created_at=created_at)
            post.created_at = created_at

            if random.random() < 0.55:
                image_file = self._download_post_image_file(f"post-{post.id}-{idx}")
                if image_file:
                    post.image.save(f"post_seed_{post.id}.jpg", image_file, save=True)

            posts.append(post)
            self._progress(idx + 1, target_posts, "Пости")
        return posts

    def _seed_comments(self, users, posts, comments_min, comments_max, days_back, batch_size):
        comments = []
        total_posts = len(posts)
        for post in posts:
            count = random.randint(comments_min, comments_max)
            if count <= 0:
                continue
            for _ in range(count):
                commenter = random.choice(users)
                comments.append(
                    Post(
                        author=commenter,
                        parent_post=post,
                        content=random.choice(COMMENT_TEXTS),
                        created_at=self._random_start_time(days_back),
                    )
                )

            self._progress(len(comments), max(total_posts, 1), "Коментарі (накопичено)", by_events=True)

        if comments:
            Post.objects.bulk_create(comments, batch_size=batch_size)
        return len(comments)

    def _seed_likes_and_bookmarks(self, users, posts, likes_max, batch_size):
        likes = []
        bookmarks = []

        for post in posts:
            if likes_max <= 0:
                continue
            liker_count = random.randint(0, min(likes_max, len(users)))
            likers = random.sample(users, liker_count)
            for liker in likers:
                likes.append(Like(user=liker, post=post))
                if random.random() < 0.35:
                    bookmarks.append(Bookmark(user=liker, post=post))

        if likes:
            Like.objects.bulk_create(likes, batch_size=batch_size, ignore_conflicts=True)
        if bookmarks:
            Bookmark.objects.bulk_create(bookmarks, batch_size=batch_size, ignore_conflicts=True)

        return len(likes), len(bookmarks)

    def _seed_reposts(self, users, posts, repost_ratio, days_back):
        repost_count = int(len(posts) * repost_ratio)
        if repost_count <= 0:
            return 0

        created = 0
        sample = random.sample(posts, min(len(posts), repost_count))
        total = len(sample)
        for index, original in enumerate(sample, start=1):
            reposter_candidates = [u for u in users if u.id != original.author_id]
            if not reposter_candidates:
                continue
            reposter = random.choice(reposter_candidates)

            repost = Post.objects.create(
                author=reposter,
                content=original.content,
                image=original.image,
                reposted_post=original,
            )
            Post.objects.filter(pk=repost.id).update(created_at=self._random_start_time(days_back))
            created += 1
            self._progress(index, total, "Репости")

        return created

    def _seed_private_threads(self, users, target_threads, min_messages, max_messages, days_back, batch_size, posts):
        existing_threads = list(self._private_thread_queryset().prefetch_related("participants"))
        existing_pairs = {
            frozenset(thread.participants.values_list("id", flat=True))
            for thread in existing_threads
        }

        threads_created = 0
        messages_created = 0
        attempts = 0
        max_attempts = max(target_threads * 20, 300)

        while len(existing_threads) < target_threads and attempts < max_attempts:
            attempts += 1
            user_a, user_b = random.sample(users, 2)
            pair_key = frozenset({user_a.id, user_b.id})
            if pair_key in existing_pairs:
                continue

            thread = ChatThread.objects.create()
            thread.participants.add(user_a, user_b)
            existing_pairs.add(pair_key)
            existing_threads.append(thread)
            threads_created += 1
            self._progress(threads_created, target_threads, "Приватні треди")

            count = random.randint(min_messages, max_messages)
            messages_created += self._fill_thread_messages(
                thread=thread,
                participants=[user_a, user_b],
                count=count,
                days_back=days_back,
                batch_size=batch_size,
                posts=posts,
            )

            for participant in (user_a, user_b):
                if random.random() < 0.15:
                    ChatThreadNotificationSetting.objects.update_or_create(
                        thread=thread,
                        user=participant,
                        defaults={"is_muted": True},
                    )

        return messages_created, threads_created

    def _seed_groups(self, users, target_groups, min_messages, max_messages, days_back, batch_size, posts):
        groups_created = 0
        messages_created = 0

        for index in range(target_groups):
            owner = random.choice(users)
            group = ChatGroup.objects.create(name=self._random_group_name(index + 1), owner=owner)

            member_limit = min(len(users), random.randint(5, 14))
            members = set(random.sample(list(users), member_limit))
            members.add(owner)

            memberships = []
            for member in members:
                role = ChatGroupMembership.Role.MEMBER
                if member.id == owner.id:
                    role = ChatGroupMembership.Role.OWNER
                elif random.random() < 0.12:
                    role = ChatGroupMembership.Role.ADMIN

                memberships.append(
                    ChatGroupMembership(
                        group=group,
                        user=member,
                        role=role,
                        is_muted_notifications=bool(random.random() < 0.1),
                    )
                )

            ChatGroupMembership.objects.bulk_create(memberships, batch_size=batch_size)

            count = random.randint(min_messages, max_messages)
            messages_created += self._fill_group_messages(
                group=group,
                members=list(members),
                count=count,
                days_back=days_back,
                batch_size=batch_size,
                posts=posts,
            )
            groups_created += 1
            self._progress(groups_created, target_groups, "Групи")

        return messages_created, groups_created

    def _fill_thread_messages(self, thread, participants, count, days_back, batch_size, posts):
        current_time = self._random_start_time(days_back)
        first_time = None
        text_messages = []
        rich_messages = []

        for idx in range(count):
            sender = random.choice(participants)
            receiver = participants[0] if sender.id != participants[0].id else participants[1]
            current_time = current_time + self._random_gap()

            is_share = posts and random.random() < 0.14
            is_image = random.random() < 0.18

            message_kwargs = {
                "thread": thread,
                "sender": sender,
                "text": self._build_share_text(random.choice(posts)) if is_share else random.choice(PRIVATE_MESSAGES),
                "created_at": current_time,
            }

            if sender.id != receiver.id and random.random() < 0.72:
                message_kwargs["read_at"] = current_time + timedelta(minutes=random.randint(1, 180))
                message_kwargs["read_by_id"] = receiver.id

            if random.random() < 0.08:
                message_kwargs["edited_at"] = current_time + timedelta(minutes=random.randint(1, 60))

            if random.random() < 0.03:
                message_kwargs["deleted_at"] = current_time + timedelta(minutes=random.randint(1, 120))

            if is_image:
                rich_messages.append((message_kwargs, f"dm-{thread.id}-{idx}"))
            else:
                text_messages.append(ChatMessage(**message_kwargs))

            if first_time is None:
                first_time = current_time

        if text_messages:
            ChatMessage.objects.bulk_create(text_messages, batch_size=batch_size)

        for kwargs, seed in rich_messages:
            message = ChatMessage.objects.create(**kwargs)
            image_file = self._download_post_image_file(seed)
            if image_file:
                message.image.save(f"chat_image_{message.id}.jpg", image_file, save=True)

        if first_time is not None:
            ChatThread.objects.filter(pk=thread.id).update(created_at=first_time, updated_at=current_time)

        return len(text_messages) + len(rich_messages)

    def _fill_group_messages(self, group, members, count, days_back, batch_size, posts):
        current_time = self._random_start_time(days_back)
        first_time = None
        messages = []

        for _ in range(count):
            sender = random.choice(members)
            current_time = current_time + self._random_gap()

            is_share = posts and random.random() < 0.25
            text = self._build_share_text(random.choice(posts)) if is_share else random.choice(GROUP_MESSAGES)

            message_kwargs = {
                "group": group,
                "sender": sender,
                "text": text,
                "created_at": current_time,
            }

            if random.random() < 0.06:
                message_kwargs["edited_at"] = current_time + timedelta(minutes=random.randint(1, 80))
            if random.random() < 0.02:
                message_kwargs["deleted_at"] = current_time + timedelta(minutes=random.randint(1, 120))

            messages.append(ChatGroupMessage(**message_kwargs))
            if first_time is None:
                first_time = current_time

        if messages:
            ChatGroupMessage.objects.bulk_create(messages, batch_size=batch_size)

        if first_time is not None:
            ChatGroup.objects.filter(pk=group.id).update(created_at=first_time, updated_at=current_time)

        return len(messages)

    def _seed_extra_shares(self, users, posts, share_count, days_back):
        if not posts or share_count <= 0:
            return 0

        created = 0
        threads = list(ChatThread.objects.prefetch_related("participants"))
        groups = list(ChatGroup.objects.all())

        for index in range(share_count):
            post = random.choice(posts)
            share_text = self._build_share_text(post)

            if threads and (not groups or random.random() < 0.65):
                thread = random.choice(threads)
                participants = list(thread.participants.all())
                if not participants:
                    continue
                sender = random.choice(participants)
                message = ChatMessage.objects.create(thread=thread, sender=sender, text=share_text)
                ChatMessage.objects.filter(pk=message.id).update(created_at=self._random_start_time(days_back))
                created += 1
                self._progress(created, share_count, "Шери")
                continue

            if groups:
                group = random.choice(groups)
                member_ids = list(
                    ChatGroupMembership.objects.filter(group=group, is_banned=False).values_list("user_id", flat=True)
                )
                if not member_ids:
                    continue
                sender_id = random.choice(member_ids)
                message = ChatGroupMessage.objects.create(group=group, sender_id=sender_id, text=share_text)
                ChatGroupMessage.objects.filter(pk=message.id).update(created_at=self._random_start_time(days_back))
                created += 1
                self._progress(created, share_count, "Шери")

        return created

    def _progress(self, current, total, label, by_events=False):
        should_print = (
            current == total
            or (current > 0 and current % self._progress_every == 0)
        )
        if not should_print:
            return

        if by_events:
            self.stdout.write(f"{label}: {current}")
            return

        percent = int((current / total) * 100) if total else 100
        self.stdout.write(f"{label}: {current}/{total} ({percent}%)")

    def _ensure_profile(self, user):
        profile, _ = Profile.objects.get_or_create(user=user)
        changed = False

        if not profile.bio:
            profile.bio = random.choice(BIO_OPTIONS)
            changed = True

        if not profile.avatar:
            avatar_file = self._download_avatar_file(user)
            if avatar_file:
                profile.avatar.save(f"seed_{user.username}.jpg", avatar_file, save=False)
                changed = True

        if changed:
            profile.save()

    def _private_thread_queryset(self):
        return ChatThread.objects.annotate(participant_count=Count("participants")).filter(participant_count=2)

    def _build_random_identity(self, existing_usernames):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        base = f"{first_name}.{last_name}".lower()
        base = "".join(ch for ch in base if ch.isalnum() or ch == ".")
        username = base
        attempt = 0

        while username in existing_usernames:
            attempt += 1
            if attempt < 8:
                username = f"{base}{random.randint(1, 9999):04d}"
            else:
                username = f"{base}.{self._random_token(4)}"

        return first_name, last_name, username

    def _random_group_name(self, serial):
        prefix = random.choice(GROUP_NAME_PREFIXES)
        suffix = random.choice(GROUP_NAME_SUFFIXES)
        random_tail = "".join(random.choices(string.ascii_uppercase, k=2))
        return f"{prefix} {suffix} {serial}-{random_tail}"

    def _build_share_text(self, post):
        preview = (post.content or "").strip()
        if len(preview) > 180:
            preview = f"{preview[:177]}..."
        post_url = f"/post/{post.pk}/"
        return f"{SHARE_TEXT_PREFIX}\n{preview}\n{post_url}" if preview else f"{SHARE_TEXT_PREFIX}\n{post_url}"

    def _download_avatar_file(self, user):
        seed = f"{user.username}-{user.id}"
        index = (abs(hash(seed)) % 99) + 1
        gender_path = "men" if abs(hash(seed + 'm')) % 2 == 0 else "women"
        urls = [
            f"https://randomuser.me/api/portraits/{gender_path}/{index}.jpg",
            f"https://picsum.photos/seed/avatar-{seed}/256/256",
        ]
        return self._download_first_available_image(urls)

    def _download_post_image_file(self, seed):
        urls = [
            f"https://picsum.photos/seed/{seed}/1280/900",
            f"https://loremflickr.com/1280/900/nature?lock={abs(hash(seed)) % 100000}",
        ]
        return self._download_first_available_image(urls)

    def _download_first_available_image(self, urls):
        for url in urls:
            content = self._fetch_image_bytes(url)
            if content:
                return ContentFile(content)
        return None

    def _fetch_image_bytes(self, url):
        cached = self._image_cache.get(url)
        if cached is not None:
            return cached

        request = urllib.request.Request(url, headers={"User-Agent": "SociopathySeeder/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=12) as response:
                content_type = (response.headers.get("Content-Type") or "").lower()
                if "image" not in content_type:
                    self._image_cache[url] = None
                    return None

                data = response.read(4 * 1024 * 1024)
                if not data:
                    self._image_cache[url] = None
                    return None

                self._image_cache[url] = data
                return data
        except (urllib.error.URLError, TimeoutError, ValueError):
            self._image_cache[url] = None
            return None

    def _random_start_time(self, days_back):
        now = timezone.now()
        back_days = random.randint(0, days_back)
        back_minutes = random.randint(0, 23 * 60)
        return now - timedelta(days=back_days, minutes=back_minutes)

    def _random_gap(self):
        return timedelta(minutes=random.randint(2, 180), seconds=random.randint(0, 59))

    def _random_token(self, length):
        alphabet = string.ascii_lowercase + string.digits
        return "".join(random.choice(alphabet) for _ in range(length))
