from seeding.parse import edges_from_tweet, reply_targets, retweet_source


def test_reply_targets_leading_block_only():
    assert reply_targets("@Erickdub sent !") == ["erickdub"]
    assert reply_targets("@a @B_2 thanks, ping @c later") == ["a", "b_2"]
    assert reply_targets("thanks @a") == []
    assert reply_targets(None) == []


def test_reply_targets_dedupes():
    assert reply_targets("@a @A @b hi") == ["a", "b"]


def test_retweet_source():
    assert retweet_source("RT @RetentionAdam: big news") == "retentionadam"
    assert retweet_source("not a retweet") is None


def test_edges_from_real_reply_record():
    rec = {
        "tweet_id": "2118268670036320271",
        "username": "MichLieben",
        "created_at": "2026-11-05T09:06:21Z",
        "text": "@ashwingupta Thanks for your comment! Here it is: https://t.co/x",
        "is_reply": True,
        "is_retweet": False,
    }
    (e,) = edges_from_tweet(rec)
    assert (e.src, e.dst, e.kind) == ("michlieben", "ashwingupta", "reply")


def test_no_self_edges_and_no_edges_for_plain_posts():
    assert edges_from_tweet({"username": "a", "is_reply": True, "text": "@a more"}) == []
    assert edges_from_tweet({"username": "a", "text": "hello", "is_reply": False}) == []
