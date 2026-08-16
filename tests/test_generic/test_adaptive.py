"""Tests for adaptive (self-healing) element relocation."""

from bs4 import BeautifulSoup

from pyscrappy.generic.adaptive import (
    _score,
    _text_is_volatile,
    fingerprint,
    relocate,
)
from pyscrappy.generic.adaptive_store import AdaptiveStore


def _el(html, selector):
    return BeautifulSoup(html, "lxml").select_one(selector)


# --- fingerprint ---


def test_fingerprint_captures_core_features():
    el = _el('<div class="list"><span id="price" class="amount">$10</span></div>', "#price")
    fp = fingerprint(el)
    assert fp["tag"] == "span"
    assert fp["id"] == "price"
    assert "amount" in fp["classes"]
    assert fp["text"] == "$10"
    assert fp["path"][-1] == "span"


def test_fingerprint_records_nearest_stable_anchor():
    html = '<section id="cart"><div><div><b class="v">42</b></div></div></section>'
    fp = fingerprint(_el(html, ".v"))
    assert fp["anchor_id"] == "id=cart"
    assert fp["anchor_tag"] == "section"
    assert fp["anchor_depth"] == 3


def test_volatility_detection():
    assert _text_is_volatile("$1,299.00")
    assert _text_is_volatile("42%")
    assert _text_is_volatile("2026-08-10")
    assert _text_is_volatile("5 min")
    assert not _text_is_volatile("Add to cart")
    assert not _text_is_volatile("Wireless Mouse")


# --- relocation across a structural change ---

# v1: the "original" page we fingerprint against.
_V1 = """
<html><body>
  <main id="content">
    <div class="product-card">
      <h2 class="title">Wireless Mouse</h2>
      <span class="price" data-testid="price">$29.99</span>
      <button class="btn buy">Add to cart</button>
    </div>
  </main>
</body></html>
"""

# v2: the site got redesigned — classes renamed, wrappers added, price changed —
# but the stable hooks (id="content", data-testid="price") and text survive.
_V2 = """
<html><body>
  <main id="content">
    <section class="grid">
      <article class="card card--v2">
        <div class="card__body">
          <h3 class="card__title heading">Wireless Mouse</h3>
          <span class="card__price money" data-testid="price">$24.99</span>
          <button class="cta primary">Add to cart</button>
        </div>
      </article>
    </section>
  </main>
</body></html>
"""


def test_relocate_finds_price_after_redesign_via_stable_hook():
    price = _el(_V1, ".price")
    fp = fingerprint(price)
    root = BeautifulSoup(_V2, "lxml")
    result = relocate(fp, root)
    assert result.element is not None
    # It relocated the price span even though its class changed and the tag moved,
    # because data-testid + tag + anchor carried it.
    assert result.element.get("data-testid") == "price"
    assert result.confidence >= 55


def test_relocate_finds_title_by_text_when_class_changes():
    title = _el(_V1, ".title")
    fp = fingerprint(title)
    root = BeautifulSoup(_V2, "lxml")
    result = relocate(fp, root)
    assert result.element is not None
    assert result.element.get_text(strip=True) == "Wireless Mouse"


def test_relocate_returns_none_below_threshold():
    fp = fingerprint(_el(_V1, ".price"))
    root = BeautifulSoup("<html><body><p>totally unrelated page</p></body></html>", "lxml")
    result = relocate(fp, root)
    assert result.element is None
    assert result.confidence < 55


def test_relocate_reports_runner_up_gap():
    fp = fingerprint(_el(_V1, ".price"))
    root = BeautifulSoup(_V2, "lxml")
    result = relocate(fp, root)
    # A decisive match: the price span should clearly lead any other <span>.
    assert result.runner_up_gap >= 0
    assert result.scored >= 1


# --- weighting: our edge over a flat average ---


def test_stable_hook_outweighs_volatile_text():
    # Two candidates: one shares the data-testid hook but has different (volatile)
    # price text; one shares nothing but happens to have similar digits. The hook
    # must win — volatile text can't carry a match on its own.
    fp = fingerprint(_el(_V1, ".price"))
    page = """
    <div id="content">
      <span data-testid="price" class="x">$0.01</span>
      <span class="y">$29.99</span>
    </div>
    """
    root = BeautifulSoup(page, "lxml")
    result = relocate(fp, root)
    assert result.element.get("data-testid") == "price"


def test_score_is_higher_for_the_true_match():
    fp = fingerprint(_el(_V1, ".price"))
    root = BeautifulSoup(_V2, "lxml")
    true_match = root.find("span", {"data-testid": "price"})
    decoy = root.find("button")
    assert _score(fp, true_match) > _score(fp, decoy)


# --- storage round-trip ---


def test_store_save_and_retrieve(tmp_path):
    store = AdaptiveStore(tmp_path / "adaptive.json")
    fp = fingerprint(_el(_V1, ".price"))
    store.save("price", fp, namespace="example.com")
    assert store.retrieve("price", namespace="example.com") == fp
    assert store.retrieve("price") is None  # namespace isolates it
    assert store.retrieve("missing", namespace="example.com") is None


def test_store_survives_missing_file(tmp_path):
    store = AdaptiveStore(tmp_path / "nope.json")
    assert store.retrieve("anything") is None


# --- end-to-end via Selector.css(adaptive=...) ---

from pyscrappy import Selector  # noqa: E402


def test_selector_css_auto_save_then_heal(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")

    # v1: normal scrape, save the price element under an id.
    page_v1 = Selector(_V1, url="https://shop.example.com/p/1", adaptive_store=store)
    hit = page_v1.css(".price", auto_save=True, adaptive_id="price")
    assert hit.get() is not None
    assert hit.adaptive_confidence is None  # a normal match, not a heal

    # v2: the ".price" class is gone; adaptive relocation heals it.
    page_v2 = Selector(_V2, url="https://shop.example.com/p/1", adaptive_store=store)
    healed = page_v2.css(".price", adaptive=True, adaptive_id="price")
    assert len(healed) == 1
    assert healed[0].attrs.get("data-testid") == "price"
    assert healed.adaptive_confidence is not None
    assert healed.adaptive_confidence >= 55


def test_selector_css_no_heal_without_adaptive_flag(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    Selector(_V1, adaptive_store=store).css(".price", auto_save=True, adaptive_id="price")
    # Without adaptive=True, a broken selector just returns empty (unchanged behavior).
    healed = Selector(_V2, adaptive_store=store).css(".price", adaptive_id="price")
    assert len(healed) == 0


def test_selector_css_namespaced_by_site(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    # Save under site A; a different site with the same id must not reuse it.
    Selector(_V1, url="https://a.com", adaptive_store=store).css(
        ".price", auto_save=True, adaptive_id="price"
    )
    other = Selector(_V2, url="https://b.com", adaptive_store=store).css(
        ".price", adaptive=True, adaptive_id="price"
    )
    assert len(other) == 0  # no fingerprint saved for b.com


def test_chained_selector_auto_save_can_heal_on_fresh_page(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    page_v1 = Selector(_V1, url="https://shop.example.com/p/1", adaptive_store=store)
    card = page_v1.css(".product-card")[0]
    card.css(".price", auto_save=True, adaptive_id="price")

    page_v2 = Selector(_V2, url="https://shop.example.com/p/2", adaptive_store=store)
    healed = page_v2.css(".missing-price", adaptive=True, adaptive_id="price")

    assert len(healed) == 1
    assert healed[0].attrs.get("data-testid") == "price"


# --- audit trail: every heal is recorded so drift stays observable ---


def test_heal_is_recorded_in_audit_log(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    Selector(_V1, url="https://shop.example.com", adaptive_store=store).css(
        ".price", auto_save=True, adaptive_id="price"
    )
    # No heal yet: only a normal save happened.
    assert store.heal_log() == []

    healed = Selector(_V2, url="https://shop.example.com", adaptive_store=store).css(
        ".price", adaptive=True, adaptive_id="price"
    )
    assert len(healed) == 1

    log = store.heal_log()
    assert len(log) == 1
    entry = log[0]
    assert entry["identifier"] == "price"
    assert entry["namespace"] == "shop.example.com"
    assert entry["confidence"] >= 55
    assert "runner_up_gap" in entry
    # before/after fingerprints make the change auditable: the price value moved
    # from the v1 markup to the v2 markup.
    assert entry["before"]["text"] == "$29.99"
    assert entry["after"]["text"] == "$24.99"
    assert "timestamp" in entry


def test_heal_log_filters_by_identifier_and_namespace(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    for site in ("https://a.com", "https://b.com"):
        Selector(_V1, url=site, adaptive_store=store).css(
            ".price", auto_save=True, adaptive_id="price"
        )
        Selector(_V2, url=site, adaptive_store=store).css(
            ".price", adaptive=True, adaptive_id="price"
        )

    assert len(store.heal_log()) == 2
    assert len(store.heal_log(namespace="a.com")) == 1
    assert store.heal_log(namespace="a.com")[0]["namespace"] == "a.com"
    assert len(store.heal_log(identifier="price")) == 2
    assert store.heal_log(identifier="nope") == []


# --- semantic contract: a heal must satisfy the caller's field invariant ---


def test_expect_contract_accepts_a_valid_heal(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    Selector(_V1, url="https://shop.example.com", adaptive_store=store).css(
        ".price", auto_save=True, adaptive_id="price"
    )
    # Contract: the healed element's text must look like a price. It does.
    healed = Selector(_V2, url="https://shop.example.com", adaptive_store=store).css(
        ".price",
        adaptive=True,
        adaptive_id="price",
        expect=lambda s: s.text().startswith("$"),
    )
    assert len(healed) == 1
    assert healed.adaptive_confidence is not None


def test_expect_contract_rejects_a_heal_that_fails_the_invariant(tmp_path):
    store = AdaptiveStore(tmp_path / "a.json")
    Selector(_V1, url="https://shop.example.com", adaptive_store=store).css(
        ".price", auto_save=True, adaptive_id="price"
    )
    # Contract the relocated element cannot satisfy: even a high structural score
    # is rejected, and nothing is written to the audit log.
    healed = Selector(_V2, url="https://shop.example.com", adaptive_store=store).css(
        ".price",
        adaptive=True,
        adaptive_id="price",
        expect=lambda s: "IMPOSSIBLE" in s.text(),
    )
    assert len(healed) == 0
    assert healed.adaptive_confidence is None
    assert store.heal_log() == []  # a rejected heal leaves no trail


# --- comparison: our weighting beats a naive uniform average ---


def _uniform_score(fp, cand):
    """A deliberately naive scorer (Scrapling-style flat average) for comparison:
    every signal counts equally. Used only to show our weighting does better."""
    from difflib import SequenceMatcher

    cfp = fingerprint(cand)
    parts = [
        1.0 if fp["tag"] == cfp["tag"] else 0.0,
        SequenceMatcher(None, fp["text"] or "", cfp["text"] or "").ratio(),
        _jaccard_local(fp["classes"], cfp["classes"]),
        SequenceMatcher(None, "/".join(fp["path"]), "/".join(cfp["path"])).ratio(),
        SequenceMatcher(None, "/".join(fp["siblings"]), "/".join(cfp["siblings"])).ratio(),
    ]
    return sum(parts) / len(parts) * 100


def _jaccard_local(a, b):
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def test_weighted_scorer_beats_uniform_on_volatile_decoy():
    # Hard case: a decoy whose volatile price text matches the original exactly,
    # vs the true element that kept its data-testid hook but changed its price.
    # Uniform averaging is fooled by the matching text + similar structure; our
    # weighting trusts the stable hook.
    fp = fingerprint(_el(_V1, ".price"))  # $29.99, data-testid=price
    page = """
    <main id="content">
      <div class="product-card">
        <span class="price" data-testid="price">$24.99</span>
      </div>
      <div class="product-card">
        <span class="price">$29.99</span>
      </div>
    </main>
    """
    root = BeautifulSoup(page, "lxml")
    true_el = root.find("span", {"data-testid": "price"})
    decoy = [s for s in root.find_all("span") if not s.get("data-testid")][0]

    # Uniform scorer is fooled: the decoy's exact-matching text pulls it ahead.
    assert _uniform_score(fp, decoy) >= _uniform_score(fp, true_el)
    # Our weighted scorer is not: the data-testid hook carries the true element.
    assert _score(fp, true_el) > _score(fp, decoy)

    # And end-to-end relocation picks the true element.
    assert relocate(fp, root).element is true_el


def test_save_atomic_no_corruption_on_write_failure(tmp_path):
    """A failed write must not corrupt the existing store."""
    store = AdaptiveStore(tmp_path / "adaptive.json")
    fp = fingerprint(_el(_V1, ".price"))
    store.save("price", fp, namespace="example.com")

    # Verify the initial save worked
    assert store.retrieve("price", namespace="example.com") == fp

    # Patch os.replace on the specific module to avoid side-effects on concurrent code
    import unittest.mock as mock

    target = "pyscrappy.generic.adaptive_store.os.replace"
    with mock.patch(target, side_effect=OSError("disk full")):
        try:
            store.save("new_key", {"fake": True}, namespace="example.com")
        except OSError:
            pass

    # The original data must survive — not be corrupted or lost
    assert store.retrieve("price", namespace="example.com") == fp
    # The failed key must not appear
    assert store.retrieve("new_key", namespace="example.com") is None
    # No leftover .tmp files
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert len(tmp_files) == 0, f"Leftover temp files: {tmp_files}"
