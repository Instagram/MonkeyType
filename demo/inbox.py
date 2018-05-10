# Copyright 2017-present, Facebook, Inc.
# All rights reserved.
"""
Sample code for MonkeyType demonstration exercise at PyCon 2018.

"""
from collections import Counter
from itertools import chain
from operator import attrgetter
from typing import Dict, List, Set

from models import (
    AggregatedItem,
    AggregatorInterface,
    CommentedEvent,
    EventType,
    FeedEntryId,
    FollowedEvent,
    LikedEvent,
    RepoInterface,
    User,
    UserId,
)


class CommentsAggregator(AggregatorInterface[CommentedEvent]):
    type = EventType.COMMENTED

    def __init__(self, repo: RepoInterface) -> None:
        self.events: List[CommentedEvent] = []
        self.user_ids: Set[UserId] = set()
        super().__init__(repo)

    def add(self, event):
        self.events.append(event)
        self.user_ids.add(event.commenter_id)

    def aggregate(self):
        users_by_id = self.repo.get_users_by_ids(self.user_ids)

        return [
            AggregatedItem(
                type=self.type,
                text=f"{users_by_id[e.commenter_id].name} commented on your post.",
                published=e.published,
            )
            for e in self.events
        ]


class LikesAggregator(AggregatorInterface[LikedEvent]):
    type = EventType.LIKED

    def __init__(self, repo: RepoInterface) -> None:
        self.events_by_feedentry_id: Dict[FeedEntryId, List[LikedEvent]] = {}
        self.user_ids: Set[UserId] = set()
        super().__init__(repo)

    def add(self, event):
        self.events_by_feedentry_id.setdefault(event.feedentry_id, []).append(event)
        self.user_ids.add(event.liker_id)

    def aggregate(self):
        feedentries_by_id = self.repo.get_feed_entries_by_ids(
            self.events_by_feedentry_id.keys()
        )
        users_by_id = self.repo.get_users_by_ids(self.user_ids)

        return [
            AggregatedItem(
                type=self.type,
                text=self._describe(events, feedentries_by_id[fid], users_by_id),
                published=max(e.published for e in events),
            )
            for fid, events in self.events_by_feedentry_id.items()
        ]

    def _describe(self, events, feedentry, users_by_id: Dict[UserId, User]):
        users = [users_by_id[e.liker_id].name for e in events]
        post_name = f'"{feedentry.caption}"'
        if len(users) == 1:
            return f"{users[0]} liked your post {post_name}."

        elif len(users) == 2:
            return f"{users[0]} and {users[1]} liked your post {post_name}."

        else:
            return (
                f"{users[0]}, {users[1]} and {len(users) - 2} others "
                f"liked your post {post_name}."
            )


class FollowersAggregator(AggregatorInterface[FollowedEvent]):
    type = EventType.FOLLOWED

    def __init__(self, repo: RepoInterface) -> None:
        self.events: List[FollowedEvent] = []
        self.user_ids: Set[UserId] = set()
        super().__init__(repo)

    def add(self, event):
        self.events.append(event)
        self.user_ids.add(event.follower_id)

    def aggregate(self):
        users_by_id = self.repo.get_users_by_ids(self.user_ids)

        return [
            AggregatedItem(
                type=self.type,
                text=f"{users_by_id[e.follower_id].name} started following you.",
                published=e.published,
            )
            for e in self.events
        ]


class Inbox:

    def __init__(self, user: User, repo: RepoInterface) -> None:
        self.user = user
        self.repo = repo
        self.events = self.repo.get_inbox_events_for_user_id(self.user.id)

    def aggregate(self):
        aggregators: List[AggregatorInterface] = [
            CommentsAggregator(self.repo),
            LikesAggregator(self.repo),
            FollowersAggregator(self.repo),
        ]
        aggregators_by_type: Dict[EventType, List[AggregatorInterface]] = {}
        for agg in aggregators:
            aggregators_by_type.setdefault(agg.type, []).append(agg)

        for event in self.events:
            for aggregator in aggregators_by_type.get(event.type, []):
                aggregator.add(event)

        items = chain.from_iterable(
            agg.aggregate() for agg in chain.from_iterable(aggregators_by_type.values())
        )

        return sorted(items, key=attrgetter("published"), reverse=True)

    def summarize(self):
        counter = Counter(e.type for e in self.events)
        clauses: List[str] = []
        likes = counter[EventType.LIKED]
        if likes:
            clauses.append(f"{likes} new like{self._pluralize(likes)}")
        follows = counter[EventType.FOLLOWED]
        if follows:
            clauses.append(f"{follows} new follower{self._pluralize(follows)}")
        comments = counter[EventType.COMMENTED]
        if comments:
            clauses.append(f"{comments} new comment{self._pluralize(comments)}")
        if not clauses:
            combined = "no new activity"
        elif len(clauses) == 1:
            combined = clauses[0]
        else:
            initial = ", ".join(clauses[:-1])
            combined = f"{initial} and {clauses[-1]}"
        return f"You have {combined}."

    def _pluralize(self, count):
        return "" if count == 1 else "s"
