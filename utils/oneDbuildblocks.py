from dataclasses import dataclass
from typing import Any, Dict, List, Tuple, Optional
import math

@dataclass
class BlockType:
    key: str                 # e.g. "115x115|<66"
    footprint: Tuple[int,int]# canonical (L,W) in cm, unordered ok
    pallets_per_block: int   # e.g. 8, 6, 4, 2, 9
    block_height_cm: int     # conservative height for constraints
    stack_count: int        # how many pallets stacked in this block type
    allowed_lengths: Tuple[int, ...]  # possible row lengths (rotation variants), e.g. (115,) or (115,77)

@dataclass
class BlockInstance:
    block_id: int
    block_type_key: str
    length_cm: int
    height_cm: int
    weight_kg: float
    value: int
    pallets: List[Dict[str,Any]]  # meta dicts of pallets included


# ---------- 1) Canonical mapping ----------
def normalize_dim_to_set(x: int, allowed: List[int], tol: int = 2) -> Optional[int]:
    """Map x to nearest allowed value within tolerance; else None."""
    best = None
    best_dist = 10**9
    for a in allowed:
        d = abs(x - a)
        if d < best_dist:
            best_dist = d
            best = a
    return best if best is not None and best_dist <= tol else None


def canonical_footprint(L: int, W: int, tol: int = 2) -> Optional[Tuple[int,int]]:
    """
    Map raw (L,W) to canonical footprint.
    Returns (Lcan, Wcan) with Lcan>=Wcan convention for keys.
    """
    # Allowed sides we expect
    allowed = [115, 108, 77]
    a = normalize_dim_to_set(L, allowed, tol=tol)
    b = normalize_dim_to_set(W, allowed, tol=tol)
    if a is None or b is None:
        return None
    Lcan, Wcan = max(a,b), min(a,b)
    return (Lcan, Wcan)


# ---------- 2) Height band classification ----------
def classify_height_band(h_cm: int) -> str:
    """Return band label used in your table."""
    if h_cm == 230:
        return "230"
    if h_cm < 66:
        return "<66"
    if 66 <= h_cm <= 89:
        return "66-89"
    if 89 < h_cm <= 130:
        return "89-130"
    # if outside known bands, still classify conservatively
    if h_cm <= 89:
        return "<89"
    return ">130"


# ---------- 3) Build block type table ----------
def build_block_type_table(Hdoor_cm: int) -> Dict[str, BlockType]:
    """
    Encodes your table as BlockType entries.
    block_height_cm should be conservative.
    Rotation: we allow both orientations by letting allowed_lengths include both sides when meaningful.
    """
    table: Dict[str, BlockType] = {}

    def add(foot: Tuple[int,int], band: str, pallets_per_block: int, stack_count: int, block_height_cm: int,
            allow_rotate: bool):
        L, W = foot
        lengths = (L, W) if allow_rotate and L != W else (L,)
        key = f"{L}x{W}|{band}"
        table[key] = BlockType(
            key=key,
            footprint=foot,
            pallets_per_block=pallets_per_block,
            block_height_cm=block_height_cm,
            stack_count=stack_count,
            allowed_lengths=tuple(sorted(set(lengths), reverse=True))
        )

    # 115x115
    add((115,115), "<66",   8, 4, 4*65,  allow_rotate=False)  # conservative: 4*65=260
    add((115,115), "66-89", 6, 3, 3*89,  allow_rotate=False)  # 267
    add((115,115), "89-130",4, 2, 2*130, allow_rotate=False)  # 260
    add((115,115), "230",   2, 1, 230,   allow_rotate=False)  # one high (as per your table)

    # 115x108 (rotation relevant if you allow rowLen=108)
    add((115,108), "<66",   8, 4, 4*65,  allow_rotate=True)
    add((115,108), "66-89", 6, 3, 3*89,  allow_rotate=True)
    add((115,108), "89-130",4, 2, 2*130, allow_rotate=True)

    # 115x77 (rotation relevant, big)
    add((115,77),  "66-89", 6, 3, 3*89,  allow_rotate=True)
    add((115,77),  "89-130",4, 2, 2*130, allow_rotate=True)

    # 77x77
    # Your corrected logic: <89 => 9 pallets per block (3-high, 3 across), 89-130 => 6 (2-high, 3 across)
    add((77,77),   "<89",   9, 3, 3*89,  allow_rotate=False)  # 267
    add((77,77),   "89-130",6, 2, 2*130, allow_rotate=False)  # 260

    return table


# ---------- 4) Main function: pallets -> blocks ----------
def build_row_blocks_from_pallets(
    meta_per_pallet: List[Dict[str,Any]],
    Hdoor_cm: int,
    tol_cm: int = 2,
    require_multiples: bool = True
) -> Tuple[List[BlockInstance], Dict[str,int], List[str]]:
    """
    Returns:
      blocks: list of BlockInstance (each is a full row-block instance)
      recommendations: dict type_key -> how many pallets to add to reach next multiple
      warnings: list of strings for any rejected pallets/types
    """
    type_table = build_block_type_table(Hdoor_cm)
    buckets: Dict[str, List[Dict[str,Any]]] = {}
    warnings: List[str] = []

    # 1) assign each pallet to a block type bucket
    for pm in meta_per_pallet:
        Lraw, Wraw, Hraw = int(pm["length"]), int(pm["width"]), int(pm["height"])
        fp = canonical_footprint(Lraw, Wraw, tol=tol_cm)
        if fp is None:
            warnings.append(f"Unknown footprint for pallet_id={pm.get('pallet_id')} dims=({Lraw},{Wraw}).")
            continue

        band = classify_height_band(Hraw)

        key = f"{fp[0]}x{fp[1]}|{band}"
        if key not in type_table:
            warnings.append(f"No block type rule for pallet_id={pm.get('pallet_id')} key={key}.")
            continue

        buckets.setdefault(key, []).append(pm)

    # 2) compute recommendations for multiples
    recommendations: Dict[str,int] = {}
    for key, plist in buckets.items():
        k = type_table[key].pallets_per_block
        rem = len(plist) % k
        if rem != 0:
            recommendations[key] = (k - rem)

    if require_multiples and any(recommendations.values()):
        # return no blocks; caller should show recommendations and stop
        return [], recommendations, warnings

    # 3) build block instances by chunking
    blocks: List[BlockInstance] = []
    block_id = 1
    for key, plist in buckets.items():
        bt = type_table[key]
        k = bt.pallets_per_block

        # chunk into groups of size k
        for start in range(0, len(plist), k):
            chunk = plist[start:start+k]
            if len(chunk) < k:
                continue

            # weight: sum actual pallet weights if present
            w_sum = 0.0
            for pm in chunk:
                w_sum += float(pm.get("weight_kg") or 0.0)

            # choose block length later (rotation handling)
            # We'll create one block instance per allowed length option.
            # BUT: to avoid double-picking, we create a group_id concept (block_physical_id)
            # and the solver must enforce at most one chosen per group.
            for Lopt in bt.allowed_lengths:
                # Compute row-block height from actual pallet heights in this chunk (cm).


                # Conservative inside this block: use tallest pallet height.
                max_pallet_h = max(int(pm["height"]) for pm in chunk)
                block_height_cm = bt.stack_count * max_pallet_h


                blocks.append(BlockInstance(
                    block_id=block_id,
                    block_type_key=key,
                    length_cm=int(Lopt),
                    height_cm=int(block_height_cm),
                    weight_kg=w_sum,
                    value=int(k),
                    pallets=chunk
                ))
            block_id += 1


    if blocks:
        print("[oneDbuildblocks] unique block heights:", sorted({b.height_cm for b in blocks})[:20])


    return blocks, recommendations, warnings