"""Dev version of the tiny-chess engine. Readable first; golf to main.py later.

0x88 board. Pieces: white P=1 N=2 B=3 R=4 Q=5 K=6, black negative.
Search: negamax alpha-beta, iterative deepening to a fixed node budget,
quiescence on captures/promotions, MVV-LVA + killer ordering, TT with
deterministic Zobrist keys. Eval: material + piece-square tables.
"""
import random

# ---- board helpers -------------------------------------------------------
# 0x88 squares: a1=0 .. h1=7, a8=112 .. h8=119. Off-board iff sq & 0x88.
FILES = "abcdefgh"
KNIGHT_D = (-33, -31, -18, -14, 14, 18, 31, 33)
KING_D = (-17, -16, -15, -1, 1, 15, 16, 17)
BISHOP_D = (-17, -15, 15, 17)
ROOK_D = (-16, -1, 1, 16)
QUEEN_D = BISHOP_D + ROOK_D
VAL = (0, 100, 320, 330, 500, 900, 0)  # by abs(piece), king 0 (never taken)

# Piece-square tables, white perspective, a1 = index 0 of the 64.
# Rows run rank 8 -> rank 1 (as usually printed); mirrored for black.
PST_P = (
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
)
PST_N = (
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
)
PST_B = (
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
)
PST_R = (
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
)
PST_Q = (
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
)
PST_K = (
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
)
PSTS = (None, PST_P, PST_N, PST_B, PST_R, PST_Q, PST_K)


def sq64(sq88):
    """0x88 square -> 0..63 with a1=0 (for PST lookup)."""
    return (sq88 >> 4) * 8 + (sq88 & 7)


def mirror64(i64):
    return i64 ^ 56


class Pos:
    __slots__ = ("b", "turn", "castle", "ep", "half")

    def __init__(self, b, turn, castle, ep, half=0):
        self.b = b            # 128-list, 0 empty, off-board squares hold 7
        self.turn = turn      # 1 white, -1 black
        self.castle = castle  # bitmask: 1 K, 2 Q, 4 k, 8 q
        self.ep = ep          # 0x88 square or -1
        self.half = half


def parse_fen(fen):
    parts = fen.split()
    b = [7] * 128
    rows = parts[0].split("/")
    for r, row in enumerate(rows):
        f = 0
        for c in row:
            if c.isdigit():
                f += int(c)
            else:
                sq = (7 - r) * 16 + f
                # P=1..K=6 white positive, p=-1..k=-6 black
                b[sq] = (("PNBRQK".index(c.upper()) + 1) if c.isupper()
                         else -("PNBRQK".index(c.upper()) + 1))
                f += 1
    for r in range(8):
        for f in range(8):
            if b[r * 16 + f] == 7:
                b[r * 16 + f] = 0
    # off-board squares (file >= 8) stay 7
    for sq in range(128):
        if sq & 0x88:
            b[sq] = 7
    turn = 1 if parts[1] == "w" else -1
    castle = 0
    if "K" in parts[2]:
        castle |= 1
    if "Q" in parts[2]:
        castle |= 2
    if "k" in parts[2]:
        castle |= 4
    if "q" in parts[2]:
        castle |= 8
    ep = -1
    if parts[3] != "-":
        ep = (8 - int(parts[3][1])) * 16 + FILES.index(parts[3][0])
    return Pos(b, turn, castle, ep, int(parts[4]) if len(parts) > 4 else 0)


# ---- move generation ------------------------------------------------------
# Moves are (from, to, promo) with promo 0 or piece code 2..5 (abs).
def gen_moves(pos, captures_only=False):
    b, turn = pos.b, pos.turn
    moves = []
    for sq in range(128):
        p = b[sq]
        if p == 0 or p == 7 or (p > 0) != (turn > 0):
            continue
        ap = abs(p)
        if ap == 1:  # pawn
            d = 16 if turn > 0 else -16
            start_rank = 1 if turn > 0 else 6
            promo_rank = 7 if turn > 0 else 0
            one = sq + d
            if b[one] == 0 and (not captures_only or (one >> 4) == promo_rank):
                rank = one >> 4
                if rank == promo_rank:
                    for pr in (5, 4, 3, 2):
                        moves.append((sq, one, pr))
                elif not captures_only:
                    moves.append((sq, one, 0))
                    if (sq >> 4) == start_rank:
                        two = sq + 2 * d
                        if b[two] == 0:
                            moves.append((sq, two, 0))
            for df in (-1, 1):
                t = sq + d + df
                if t & 0x88:
                    continue
                v = b[t]
                if v != 0 and v != 7 and (v > 0) != (turn > 0):
                    rank = t >> 4
                    if rank == promo_rank:
                        for pr in (5, 4, 3, 2):
                            moves.append((sq, t, pr))
                    else:
                        moves.append((sq, t, 0))
                elif t == pos.ep and pos.ep != -1:
                    moves.append((sq, t, 0))
        elif ap == 2 or ap == 6:  # knight, king
            for d in KNIGHT_D if ap == 2 else KING_D:
                t = sq + d
                if t & 0x88:
                    continue
                v = b[t]
                if v == 0:
                    if not captures_only:
                        moves.append((sq, t, 0))
                elif v != 7 and (v > 0) != (turn > 0):
                    moves.append((sq, t, 0))
        else:  # sliders
            for d in BISHOP_D if ap == 3 else ROOK_D if ap == 4 else QUEEN_D:
                t = sq + d
                while not (t & 0x88):
                    v = b[t]
                    if v == 0:
                        if not captures_only:
                            moves.append((sq, t, 0))
                    else:
                        if v != 7 and (v > 0) != (turn > 0):
                            moves.append((sq, t, 0))
                        break
                    t += d
    # castling (quiet only): king may not cross or land on an attacked square
    if not captures_only:
        if turn > 0:
            if (pos.castle & 1 and b[5] == 0 and b[6] == 0 and b[7] == 4 and b[4] == 6
                    and not attacked(b, 4, -1) and not attacked(b, 5, -1) and not attacked(b, 6, -1)):
                moves.append((4, 6, 0))
            if (pos.castle & 2 and b[3] == 0 and b[2] == 0 and b[1] == 0 and b[0] == 4 and b[4] == 6
                    and not attacked(b, 4, -1) and not attacked(b, 3, -1) and not attacked(b, 2, -1)):
                moves.append((4, 2, 0))
        else:
            if (pos.castle & 4 and b[117] == 0 and b[118] == 0 and b[119] == 4 and b[116] == -6
                    and not attacked(b, 116, 1) and not attacked(b, 117, 1) and not attacked(b, 118, 1)):
                moves.append((116, 118, 0))
            if (pos.castle & 8 and b[115] == 0 and b[114] == 0 and b[113] == 0 and b[112] == 4 and b[116] == -6
                    and not attacked(b, 116, 1) and not attacked(b, 115, 1) and not attacked(b, 114, 1)):
                moves.append((116, 114, 0))
    return moves


def king_square(b, turn):
    k = 6 if turn > 0 else -6
    for sq in range(128):
        if b[sq] == k:
            return sq
    return -1


def attacked(b, sq, by):
    """Is sq attacked by side `by` (1 white, -1 black)?"""
    # pawns
    d = -16 if by > 0 else 16
    for df in (-1, 1):
        t = sq + d + df
        if not (t & 0x88) and b[t] == by * 1:
            return True
    for d in KNIGHT_D:
        t = sq + d
        if not (t & 0x88) and b[t] == by * 2:
            return True
    for d in KING_D:
        t = sq + d
        if not (t & 0x88) and b[t] == by * 6:
            return True
    for d in BISHOP_D:
        t = sq + d
        while not (t & 0x88):
            v = b[t]
            if v != 0:
                if v == by * 3 or v == by * 5:
                    return True
                break
            t += d
    for d in ROOK_D:
        t = sq + d
        while not (t & 0x88):
            v = b[t]
            if v != 0:
                if v == by * 4 or v == by * 5:
                    return True
                break
            t += d
    return False


def make_move(pos, mv):
    """Apply mv, return (new Pos, captured piece code). Assumes pseudo-legal."""
    b = pos.b[:]
    f, t, pr = mv
    p = b[f]
    cap = b[t]
    b[t] = p
    b[f] = 0
    ep = -1
    castle = pos.castle
    # en passant capture
    if abs(p) == 1 and t == pos.ep and cap == 0:
        cap = b[t - 16] if pos.turn > 0 else b[t + 16]
        b[t - 16 if pos.turn > 0 else t + 16] = 0
        cap = -pos.turn * 1
    # double push sets ep
    if abs(p) == 1 and abs(t - f) == 32:
        ep = (f + t) // 2
    # promotion
    if pr:
        b[t] = pos.turn * pr
    # castling rook
    if abs(p) == 6 and abs(t - f) == 2:
        if t == 6:
            b[5], b[7] = 4, 0
        elif t == 2:
            b[3], b[0] = 4, 0
        elif t == 118:
            b[117], b[119] = -4, 0
        elif t == 114:
            b[115], b[112] = -4, 0
    # castle rights
    if f == 4 or t == 4:
        castle &= ~3
    if f == 116 or t == 116:
        castle &= ~12
    if f == 7 or t == 7:
        castle &= ~1
    if f == 0 or t == 0:
        castle &= ~2
    if f == 119 or t == 119:
        castle &= ~4
    if f == 112 or t == 112:
        castle &= ~8
    # rook captured on its home square
    if t == 7:
        castle &= ~1
    if t == 0:
        castle &= ~2
    if t == 119:
        castle &= ~4
    if t == 112:
        castle &= ~8
    return Pos(b, -pos.turn, castle, ep), cap


def legal_moves(pos):
    out = []
    for mv in gen_moves(pos):
        np, _ = make_move(pos, mv)
        if not attacked(np.b, king_square(np.b, pos.turn), -pos.turn):
            out.append(mv)
    return out


# ---- evaluation -----------------------------------------------------------
def evaluate(pos):
    b = pos.b
    score = 0
    for sq in range(128):
        p = b[sq]
        if p == 0 or p == 7:
            continue
        ap = abs(p)
        i64 = sq64(sq)
        # Tables are written rank 8 first: white reads them flipped (i^56),
        # black reads them as written (its 7th rank is white's 2nd).
        v = VAL[ap] + PSTS[ap][(i64 ^ 56) if p > 0 else i64]
        score += v if p > 0 else -v
    return score if pos.turn > 0 else -score


# ---- search ----------------------------------------------------------------
_rng = random.Random(20261115)
ZOB = [[_rng.getrandbits(64) for _ in range(13)] for _ in range(128)]
ZOB_TURN = _rng.getrandbits(64)


def zobrist(pos):
    h = 0
    for sq in range(128):
        p = pos.b[sq]
        if p != 0 and p != 7:
            h ^= ZOB[sq][p + 6]
    if pos.turn < 0:
        h ^= ZOB_TURN
    return h


class Searcher:
    def __init__(self, nodes=30000):
        self.nodes = nodes
        self.count = 0
        self.tt = {}
        self.killers = {}

    def search_root(self, pos, legal):
        self.count = 0
        self.tt = {}
        self.killers = {}
        best = legal[0]
        best_val = -10**9
        # iterative deepening: keep deepening while the node budget allows
        depth = 1
        while True:
            val, mv = self._root(pos, legal, depth)
            if self.count > self.nodes:
                break
            if mv is not None:
                best, best_val = mv, val
            depth += 1
            if depth > 64 or self.count > self.nodes:
                break
        return best

    def _root(self, pos, legal, depth):
        alpha = -10**9
        best_mv = None
        best_val = -10**9
        ordered = self._order(pos, legal, 0)
        for mv in ordered:
            np, _ = make_move(pos, mv)
            if attacked(np.b, king_square(np.b, pos.turn), -pos.turn):
                continue
            v = -self._search(np, depth - 1, -10**9, -alpha, 1)
            if self.count > self.nodes:
                return best_val, best_mv
            if v > best_val:
                best_val, best_mv = v, mv
            if v > alpha:
                alpha = v
        return best_val, best_mv

    def _order(self, pos, moves, ply):
        def key(mv):
            f, t, pr = mv
            v = pos.b[t]
            s = 0
            if v != 0 and v != 7:
                s = 10000 + VAL[abs(v)] * 10 - VAL[abs(pos.b[f])] // 10
            if pr:
                s += 9000 + pr
            if self.killers.get(ply) == mv:
                s += 5000
            return -s
        return sorted(moves, key=key)

    def _search(self, pos, depth, alpha, beta, ply):
        self.count += 1
        if self.count > self.nodes:
            return evaluate(pos)
        if depth <= 0:
            return self._quiesce(pos, alpha, beta, ply)
        # transposition table
        h = zobrist(pos)
        ent = self.tt.get(h)
        tt_move = None
        if ent and ent[0] >= depth:
            _, flag, val, tt_move = ent
            if flag == 0:
                return val
            if flag == 1 and val >= beta:
                return val
            if flag == 2 and val <= alpha:
                return val
        moves = legal_moves(pos)
        if not moves:
            if attacked(pos.b, king_square(pos.b, pos.turn), -pos.turn):
                return -100000 + ply
            return 0
        ordered = self._order(pos, moves, ply)
        if tt_move is not None and tt_move in ordered:
            ordered.remove(tt_move)
            ordered.insert(0, tt_move)
        best = -10**9
        best_mv = None
        orig_alpha = alpha
        for mv in ordered:
            np, _ = make_move(pos, mv)
            v = -self._search(np, depth - 1, -beta, -alpha, ply + 1)
            if self.count > self.nodes:
                return best if best != -10**9 else evaluate(pos)
            if v > best:
                best, best_mv = v, mv
            if v > alpha:
                alpha = v
                if alpha >= beta:
                    if pos.b[mv[1]] == 0:
                        self.killers[ply] = mv
                    break
        flag = 0 if best <= orig_alpha else 1 if best >= beta else 2
        # store: flag 0 exact, 1 lower, 2 upper (best vs orig_alpha/beta)
        if best >= beta:
            flag = 1
        elif best <= orig_alpha:
            flag = 2
        else:
            flag = 0
        self.tt[h] = (depth, flag, best, best_mv)
        return best

    def _quiesce(self, pos, alpha, beta, ply):
        self.count += 1
        in_check = attacked(pos.b, king_square(pos.b, pos.turn), -pos.turn)
        if not in_check:
            stand = evaluate(pos)
            if stand >= beta:
                return beta
            if stand > alpha:
                alpha = stand
        moves = (legal_moves(pos) if in_check
                 else gen_moves(pos, captures_only=True))
        for mv in self._order(pos, moves, ply):
            np, _ = make_move(pos, mv)
            if attacked(np.b, king_square(np.b, pos.turn), -pos.turn):
                continue
            v = -self._quiesce(np, -beta, -alpha, ply + 1)
            if v > alpha:
                alpha = v
                if alpha >= beta:
                    break
        return alpha


def move_to_uci(mv):
    f, t, pr = mv
    s = FILES[f & 7] + str((f >> 4) + 1) + FILES[t & 7] + str((t >> 4) + 1)
    if pr:
        s += "nbrq"[pr - 2]
    return s



ENV_URL =  os.environ.get("MAKEFUN_ENV_URL") or sys.exit("MAKEFUN_ENV_URL is not set")
NODES = int(os.environ.get("CHESS_NODES", "30000"))


def post(path, body):
    req = urllib.request.Request(
        ENV_URL + path,
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode(errors='replace')}")


def uci_to_move(uci):
    f = FILES.index(uci[0]) + (int(uci[1]) - 1) * 16
    t = FILES.index(uci[2]) + (int(uci[3]) - 1) * 16
    pr = 0
    if len(uci) == 5:
        pr = "nbrq".index(uci[4]) + 2
    return (f, t, pr)


s = Searcher(NODES)
while True:
    g = post("/game", {})
    if g["status"] == "done":
        break
    while g["status"] == "your_move":
        pos = parse_fen(g["fen"])
        legal = [uci_to_move(u) for u in g["legal_moves"]]
        # keep only moves my own generator also finds (sanity), else trust env
        mine = legal_moves(pos)
        mine_set = set(mine)
        cand = [m for m in legal if m in mine_set] or legal
        mv = s.search_root(pos, cand)
        g = post("/move", {"game": g["game"], "move": move_to_uci(mv)})
    print(f"game {g['game']}: {g['outcome']} by {g['reason']}", file=sys.stderr)
print(f"done: {g.get('wins')} won, {g.get('draws')} drawn, {g.get('losses')} lost", file=sys.stderr)
