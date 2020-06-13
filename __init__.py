"""Python bindings to the Cold Clear Tetris Bot as of commit 6d0832d.
Requires the `cold_clear` dynamic library (Not provided in this repo.)
"""
from __future__ import annotations
import ctypes
import enum
from typing import List, Generator

COLD_CLEAR_LIB = None
"""The Cold Clear dynamic library."""

def init(path):
    """Loads the dynamic library. Make sure to call this function before using this module."""
    global COLD_CLEAR_LIB
    if COLD_CLEAR_LIB == None:
        COLD_CLEAR_LIB = ctypes.cdll.LoadLibrary(path)
        COLD_CLEAR_LIB.cc_launch_async.restype = ctypes.c_void_p
        COLD_CLEAR_LIB.cc_destroy_async.restype = None
        COLD_CLEAR_LIB.cc_reset_async.restype = None
        COLD_CLEAR_LIB.cc_add_next_piece_async.restype = None
        COLD_CLEAR_LIB.cc_request_next_move.restype = None
        COLD_CLEAR_LIB.cc_poll_next_move.restype = ctypes.c_int
        COLD_CLEAR_LIB.cc_block_next_move.restype = ctypes.c_int
        COLD_CLEAR_LIB.cc_default_options.restype = None
        COLD_CLEAR_LIB.cc_default_weights.restype = None
        COLD_CLEAR_LIB.cc_fast_weights.restype = None

class CCPiece(enum.IntEnum):
    I = 0
    T = 1
    O = 2
    S = 3
    Z = 4
    L = 5
    J = 6

class CCTspinStatus(enum.IntEnum):
    NONE = 0
    MINI = 1
    FULL = 2


class CCMovement(enum.IntEnum):
    LEFT = 0
    RIGHT = 1
    CW = 2
    CCW = 3
    DROP = 4

class CCMovementMode(enum.IntEnum):
    ZERO_G = 0
    TWENTY_G = 1
    HARD_DROP_ONLY = 2

class CCBotPollStatus(enum.IntEnum):
    MOVE_PROVIDED = 0
    WAITING = 1
    DEAD = 2

class CCPlanPlacement(ctypes.Structure):
    _fields_ = [
        ("piece", ctypes.c_int),
        ("tspin", ctypes.c_int),

        # Expected cell coordinates of placement, (0, 0) being the bottom left
        ("expected_x", ctypes.c_uint8 * 4),
        ("expected_y", ctypes.c_uint8 * 4),

        # Expected lines that will be cleared after placement, with -1 indicating no line
        ("cleared_lines", ctypes.c_int32 * 4)
    ]

    def expected_cells_iter(self) -> Generator[(int, int), None, None]:
        """Returns an iterator over the expected cell coordinates of the placement."""
        for i in range(4):
            yield self.expected_x[i], self.expected_y[i]

class CCMove(ctypes.Structure):
    _fields_ = [
        # Whether hold is required
        ("hold", ctypes.c_bool),
        # Expected cell coordinates of placement, (0, 0) being the bottom left
        ("expected_x", ctypes.c_uint8 * 4),
        ("expected_y", ctypes.c_uint8 * 4),
        # Number of moves in the path
        ("movement_count", ctypes.c_uint8),
        # Movements
        ("movements", ctypes.c_int * 32),

        # Bot Info
        ("nodes", ctypes.c_uint32),
        ("depth", ctypes.c_uint32),
        ("original_rank", ctypes.c_uint32)
    ]

    def expected_cells_iter(self) -> Generator[(int, int), None, None]:
        """Returns an iterator over the expected cell coordinates of the placement."""
        for i in range(4):
            yield self.expected_x[i], self.expected_y[i]

    def movements_iter(self) -> Generator[CCMovement, None, None]:
        """Returns an iterator over the movements for this move."""
        for i in range(self.movement_count):
            yield self.movements[i]

class CCOptions(ctypes.Structure):
    _fields_ = [
        ("mode", ctypes.c_int),
        ("use_hold", ctypes.c_bool),
        ("speculate", ctypes.c_bool),
        ("pcloop", ctypes.c_bool),
        ("min_nodes", ctypes.c_uint32),
        ("max_nodes", ctypes.c_uint32),
        ("threads", ctypes.c_uint32)
    ]

    @staticmethod
    def default() -> CCOptions:
        """Returns the default options."""
        options = CCOptions()
        COLD_CLEAR_LIB.cc_default_options(ctypes.byref(options))
        return options

class CCWeights(ctypes.Structure):
    _fields_ = [
        ("back_to_back", ctypes.c_int32),
        ("bumpiness", ctypes.c_int32),
        ("bumpiness_sq", ctypes.c_int32),
        ("height", ctypes.c_int32),
        ("top_half", ctypes.c_int32),
        ("top_quarter", ctypes.c_int32),
        ("jeopardy", ctypes.c_int32),
        ("cavity_cells", ctypes.c_int32),
        ("cavity_cells_sq", ctypes.c_int32),
        ("overhang_cells", ctypes.c_int32),
        ("overhang_cells_sq", ctypes.c_int32),
        ("covered_cells", ctypes.c_int32),
        ("covered_cells_sq", ctypes.c_int32),
        ("tslot", ctypes.c_int32 * 4),
        ("well_depth", ctypes.c_int32),
        ("max_well_depth", ctypes.c_int32),
        ("well_column", ctypes.c_int32 * 10),

        ("b2b_clear", ctypes.c_int32),
        ("clear1", ctypes.c_int32),
        ("clear2", ctypes.c_int32),
        ("clear3", ctypes.c_int32),
        ("clear4", ctypes.c_int32),
        ("tspin1", ctypes.c_int32),
        ("tspin2", ctypes.c_int32),
        ("tspin3", ctypes.c_int32),
        ("mini_tspin1", ctypes.c_int32),
        ("mini_tspin2", ctypes.c_int32),
        ("perfect_clear", ctypes.c_int32),
        ("combo_garbage", ctypes.c_int32),
        ("move_time", ctypes.c_int32),
        ("wasted_t", ctypes.c_int32),

        ("use_bag", ctypes.c_bool)
    ]

    @staticmethod
    def default() -> CCWeights:
        """Returns the default weights."""
        weights = CCWeights()
        COLD_CLEAR_LIB.cc_default_weights(ctypes.byref(weights))
        return weights

    @staticmethod
    def fast() -> CCWeights:
        """Returns the fast weights."""
        weights = CCWeights()
        COLD_CLEAR_LIB.cc_fast_weights(ctypes.byref(weights))
        return weights

class CCHandle:
    def __init__(self, options, weights):
        """Launches a bot thread with a blank board, empty queue, and all seven pieces in the bag,
        using the specified options and weights. Do not forget to call `terminate` after you are
        done with the bot. Alternatively, you can use a `with` statement to handle this automatically.
        """
        # `ctypes.c_void_p` is special in that if it's returned from a C function it gets converted
        # to a python `int` or something, so it has to be `cast`ed back into a void pointer to
        # actually be useful. Go figure.
        self._handle = ctypes.cast(COLD_CLEAR_LIB.cc_launch_async(ctypes.byref(options), ctypes.byref(weights)), ctypes.c_void_p)
    
    def terminate(self):
        """Terminates the handle and frees the memory associated with the bot. Do not forget to call
        this function after you are done with the bot. Alternatively, you can use a `with` statement
        to handle this automatically.
        """
        if self._handle != None:
            COLD_CLEAR_LIB.cc_destroy_async(self._handle)
            self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.terminate()

    def reset(self, field, b2b, combo):
        """Resets the playfield, back-to-back status, and combo count.
  
        This should only be used when garbage is received or when your client could not place the
        piece in the correct position for some reason (e.g. 15 move rule), since this forces the
        bot to throw away previous computations.
  
        Note: combo is not the same as the displayed combo in guideline games. Here, it is the
        number of consecutive line clears achieved. So, generally speaking, if "x Combo" appears
        on the screen, you need to use x+1 here.
  
        The field parameter is an iterable of 40 rows, which are iterables of 10 bools. The first
        element of the first row is the bottom-left cell.
        """
        raw_field = (ctypes.c_bool * 400)()
        for y, row in enumerate(field):
            for x, cell in enumerate(row):
                raw_field[x + y * 10] = cell
        COLD_CLEAR_LIB.cc_reset_async(self._handle, ctypes.byref(raw_field), ctypes.c_bool(b2b), ctypes.c_uint32(combo))

    def add_next_piece(self, piece):
        """Adds a new piece to the end of the queue.
         
        If speculation is enabled, the piece must be in the bag. For example, if you start a new
        game with starting sequence IJOZT, the first time you call this function you can only
        provide either an L or an S piece.
        """
        COLD_CLEAR_LIB.cc_add_next_piece_async(self._handle, ctypes.c_int(piece))

    def request_next_move(self, incoming):
        """Request the bot to provide a move as soon as possible.

        In most cases, "as soon as possible" is a very short amount of time, and is only longer if
        the provided lower limit on thinking has not been reached yet or if the bot cannot provide
        a move yet, usually because it lacks information on the next pieces.

        For example, in a game with zero piece previews and hold enabled, the bot will never be able
        to provide the first move because it cannot know what piece it will be placing if it chooses
        to hold. Another example: in a game with zero piece previews and hold disabled, the bot
        will only be able to provide a move after the current piece spawns and you provide the piece
        information to the bot using `cc_add_next_piece_async`.

        It is recommended that you call this function the frame before the piece spawns so that the
        bot has time to finish its current thinking cycle and supply the move.

        Once a move is chosen, the bot will update its internal state to the result of the piece
        being placed correctly and the move will become available by calling `cc_poll_next_move`.

        The incoming parameter specifies the number of lines of garbage the bot is expected to receive
        after placing the next piece.
        """
        COLD_CLEAR_LIB.cc_request_next_move(self._handle, ctypes.c_uint32(incoming))

    def _next_move_fn(self, fn, plan_length) -> (CCBotPollStatus, CCMove, List[CCBotPollStatus]):
        move = CCMove()
        plan = (CCPlanPlacement * plan_length)()
        plan_ptr = None
        if plan_length > 0:
            plan_ptr = ctypes.byref(plan)
        raw_plan_length = ctypes.c_uint32(plan_length)
        status = fn(self._handle, ctypes.byref(move), plan_ptr, ctypes.byref(raw_plan_length))
        return status, move, plan[0:raw_plan_length.value]

    def poll_next_move(self, plan_length = 0) -> (CCBotPollStatus, CCMove, List[CCBotPollStatus]):
        """Checks to see if the bot has provided the previously requested move yet.
        
        The returned move contains both a path and the expected location of the placed piece. The
        returned path is reasonably good, but you might want to use your own pathfinder to, for
        example, exploit movement intricacies in the game you're playing.

        If the piece couldn't be placed in the expected location, you must call `cc_reset_async` to
        reset the game field, back-to-back status, and combo values.

        If `plan` and `plan_length` are not `NULL` and this function provides a move, a placement plan
        will be returned in the array pointed to by `plan`. `plan_length` should point to the length
        of the array, and the number of plan placements provided will be returned through this pointer.

        If the move has been provided, this function will return `CCBotPollStatus.MOVE_PROVIDED`.
        If the bot has not produced a result, this function will return `CCBotPollStatus.WAITING`.
        If the bot has found that it cannot survive, this function will return `CCBotPollStatus.DEAD`
        """
        return self._next_move_fn(COLD_CLEAR_LIB.cc_poll_next_move, plan_length)

    def block_next_move(self, plan_length = 0) -> (CCBotPollStatus, CCMove, List[CCBotPollStatus]):
        """This function is the same as `cc_poll_next_move` except when `cc_poll_next_move` would return
        `CC_WAITING` it instead waits until the bot has made a decision.
        
        If the move has been provided, this function will return `CC_MOVE_PROVIDED`.
        If the bot has found that it cannot survive, this function will return `CC_BOT_DEAD`
        """
        return self._next_move_fn(COLD_CLEAR_LIB.cc_block_next_move, plan_length)

if __name__ == "__main__":
    from pathlib import Path
    import collections
    import random
    import time
    
    print("Starting demo.")

    dll_path = ""
    while dll_path == "":
        path = Path(input("Please type in the path to the Cold Clear dynamic library: ").strip())
        if path.is_file():
            dll_path = path.resolve(False).as_posix()
        else:
            print("Invalid path.")
    init(dll_path)

    with CCHandle(CCOptions.default(), CCWeights.default()) as bot:
        field = [[False for x in range(10)] for y in range(40)]
        queue = collections.deque()
        bag = list(CCPiece)
        random.shuffle(bag)
        while len(queue) < 5:
            piece = bag.pop()
            queue.append(piece)
            bot.add_next_piece(piece)
        hold = None
        while True:
            time.sleep(0.5)
            bot.request_next_move(0)

            status, move, plan = bot.block_next_move(0)
            if status == CCBotPollStatus.DEAD:
                print("Oh no! Cold Clear died.")
                break

            if move.hold:
                prev_hold = hold
                hold = queue.popleft()
                if prev_hold == None:
                    queue.popleft()
            else:
                queue.popleft()

            while len(queue) < 5:
                if len(bag) == 0:
                    bag = list(CCPiece)
                    random.shuffle(bag)
                piece = bag.pop()
                queue.append(piece)
                bot.add_next_piece(piece)

            for i in range(4):
                field[move.expected_y[i]][move.expected_x[i]] = True

            field = [row for row in field if not all(row)]
            while len(field) < 40:
                field.append([False for x in range(10)])

            for y in reversed(range(20)):
                for cell in field[y]:
                    print("[]" if cell else "..", end="")
                print()
                
            hold_char = " "
            if hold != None:
                hold_char = hold.name
            print(f"H: [{hold_char}] Q: [", end="")
            for i, piece in enumerate(queue):
                if i < 5:
                    if i > 0:
                        print(", ", end="")
                    print(piece.name, end="")
                else:
                    break
            print("]")
            print()