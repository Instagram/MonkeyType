# Copyright 2017-present, Facebook, Inc.
# All rights reserved.
"""
Sample code for MonkeyType demonstration exercise at PyCon 2018.

"""
import sys
from datetime import datetime, timedelta
from typing import Collection, Dict, List, Optional

import inbox
import models


class FakeRepo(models.RepoInterface):

    def __init__(self, *objs: object) -> None:
        self.objs = objs

    def get_feed_entries_by_ids(
        self, ids: Collection[models.FeedEntryId]
    ) -> Dict[models.FeedEntryId, Optional[models.FeedEntry]]:
        found = {
            f.id: f
            for f in self.objs
            if isinstance(f, models.FeedEntry) and f.id in ids
        }
        return {id: found.get(id) for id in ids}

    def get_feed_entries_for_user_id(
        self, user_id: models.UserId
    ) -> List[models.FeedEntry]:
        return [
            o
            for o in self.objs
            if isinstance(o, models.FeedEntry) and o.user_id == user_id
        ]

    def get_users_by_ids(
        self, ids: Collection[models.UserId]
    ) -> Dict[models.UserId, Optional[models.User]]:
        found = {
            u.id: u for u in self.objs if isinstance(u, models.User) and u.id in ids
        }
        return {id: found.get(id) for id in ids}

    def get_inbox_events_for_user_id(
        self, user_id: models.UserId
    ) -> List[models.InboxEvent]:
        return [
            o
            for o in self.objs
            if isinstance(o, models.InboxEvent) and o.user_id == user_id
        ]


last_auto_id = 0


def make_user(**kwargs):
    global last_auto_id
    last_auto_id += 1
    defaults = {"id": models.UserId(last_auto_id), "name": "Test User", "following": []}
    defaults.update(kwargs)
    return models.User(**defaults)


def now():
    if sys.platform != 'win32':
        return datetime.now()

    # Workaround for Windows where two close call to datetime.now() return
    # exactly the same datetime
    return datetime.now() + timedelta(microseconds=last_auto_id)


def make_feedentry(**kwargs):
    global last_auto_id
    last_auto_id += 1
    defaults = {
        "id": models.FeedEntryId(last_auto_id),
        "caption": "Test FeedEntry",
        "published": now(),
    }
    defaults.update(kwargs)
    return models.FeedEntry(**defaults)


def make_commented(**kwargs):
    global last_auto_id
    last_auto_id += 1
    defaults = {
        "id": models.InboxEventId(last_auto_id),
        "comment_text": "Test comment",
        "published": now(),
    }
    defaults.update(kwargs)
    return models.CommentedEvent(**defaults)


def make_liked(**kwargs):
    global last_auto_id
    last_auto_id += 1
    defaults = {"id": models.InboxEventId(last_auto_id), "published": now()}
    defaults.update(kwargs)
    return models.LikedEvent(**defaults)


def make_followed(**kwargs):
    global last_auto_id
    last_auto_id += 1
    defaults = {"id": models.InboxEventId(last_auto_id), "published": now()}
    defaults.update(kwargs)
    return models.FollowedEvent(**defaults)


def test_empty_inbox():
    u = make_user()
    repo = FakeRepo(u)
    box = inbox.Inbox(u, repo)

    assert box.aggregate() == []
    assert box.summarize() == "You have no new activity."


def test_commented():
    u = make_user()
    other = make_user(name="Commenter")
    feedentry = make_feedentry(user_id=u.id)
    commented = make_commented(
        user_id=u.id, feedentry_id=feedentry.id, commenter_id=other.id
    )
    repo = FakeRepo(u, other, feedentry, commented)
    box = inbox.Inbox(u, repo)

    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.COMMENTED,
                text="Commenter commented on your post.",
                published=commented.published,
            )
        ]
    )
    assert box.summarize() == "You have 1 new comment."


def test_followed():
    u = make_user()
    other = make_user(name="Follower", following=[u.id])
    event = make_followed(user_id=u.id, follower_id=other.id)
    repo = FakeRepo(u, other, event)
    box = inbox.Inbox(u, repo)

    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.FOLLOWED,
                text="Follower started following you.",
                published=event.published,
            )
        ]
    )
    assert box.summarize() == "You have 1 new follower."


def test_one_like():
    u = make_user()
    liker = make_user(name="Liker")
    feedentry = make_feedentry(user_id=u.id, caption="My Post")
    event = make_liked(user_id=u.id, liker_id=liker.id, feedentry_id=feedentry.id)
    repo = FakeRepo(u, liker, feedentry, event)
    box = inbox.Inbox(u, repo)

    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.LIKED,
                text='Liker liked your post "My Post".',
                published=event.published,
            )
        ]
    )
    assert box.summarize() == "You have 1 new like."


def test_two_likes():
    u = make_user()
    liker1 = make_user(name="Liker One")
    liker2 = make_user(name="Liker Two")
    feedentry = make_feedentry(user_id=u.id, caption="My Post")
    like1 = make_liked(user_id=u.id, liker_id=liker1.id, feedentry_id=feedentry.id)
    like2 = make_liked(user_id=u.id, liker_id=liker2.id, feedentry_id=feedentry.id)
    repo = FakeRepo(u, liker1, liker2, feedentry, like1, like2)
    box = inbox.Inbox(u, repo)

    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.LIKED,
                text='Liker One and Liker Two liked your post "My Post".',
                published=like2.published,
            )
        ]
    )
    assert box.summarize() == "You have 2 new likes."


def test_three_likes():
    u = make_user()
    liker1 = make_user(name="Liker One")
    liker2 = make_user(name="Liker Two")
    liker3 = make_user(name="Liker Three")
    feedentry = make_feedentry(user_id=u.id, caption="My Post")
    like1 = make_liked(user_id=u.id, liker_id=liker1.id, feedentry_id=feedentry.id)
    like2 = make_liked(user_id=u.id, liker_id=liker2.id, feedentry_id=feedentry.id)
    like3 = make_liked(user_id=u.id, liker_id=liker3.id, feedentry_id=feedentry.id)
    repo = FakeRepo(u, liker1, liker2, liker3, feedentry, like1, like2, like3)
    box = inbox.Inbox(u, repo)

    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.LIKED,
                text='Liker One, Liker Two and 1 others liked your post "My Post".',
                published=like3.published,
            )
        ]
    )
    assert box.summarize() == "You have 3 new likes."


def test_everything():
    u = make_user()
    other = make_user(name="Other", following=[u.id])
    first_entry = make_feedentry(user_id=u.id, caption="My First Post")
    follow = make_followed(user_id=u.id, follower_id=other.id)
    second_entry = make_feedentry(user_id=u.id, caption="Second Post")
    like1 = make_liked(user_id=u.id, liker_id=other.id, feedentry_id=first_entry.id)
    comment = make_commented(
        user_id=u.id, commenter_id=other.id, feedentry_id=first_entry.id
    )
    like2 = make_liked(user_id=u.id, liker_id=other.id, feedentry_id=second_entry.id)
    repo = FakeRepo(u, other, first_entry, second_entry, like1, like2, comment, follow)
    box = inbox.Inbox(u, repo)
    assert (
        box.aggregate()
        == [
            models.AggregatedItem(
                type=models.EventType.LIKED,
                text='Other liked your post "Second Post".',
                published=like2.published,
            ),
            models.AggregatedItem(
                type=models.EventType.COMMENTED,
                text="Other commented on your post.",
                published=comment.published,
            ),
            models.AggregatedItem(
                type=models.EventType.LIKED,
                text='Other liked your post "My First Post".',
                published=like1.published,
            ),
            models.AggregatedItem(
                type=models.EventType.FOLLOWED,
                text="Other started following you.",
                published=follow.published,
            ),
        ]
    )
    assert box.summarize() == "You have 2 new likes, 1 new follower and 1 new comment."


def test_aggregator_interface():
    agg = inbox.AggregatorInterface(FakeRepo())

    agg.add(
        models.InboxEvent(
            models.InboxEventId(1), models.UserId(2), published=now()
        )
    )
    assert agg.aggregate() == []
