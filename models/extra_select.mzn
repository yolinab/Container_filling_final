%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
% extra_select.mzn
% Choose how many extra pallets of each type to add, given
% a scalar free floor length (aggregated) and buffer.
%
% INPUT:
%   int: T;                      % number of pallet types
%   array[1..T] of int: len;     % length in Y
%   array[1..T] of int: wid;     % width in X
%   array[1..T] of int: hgt;     % height in Z
%   int: BUF;                    % buffer between pallets along Y
%   int: free_len;               % total free floor length along Y
%   array[1..T] of int: max_add; % max extra pallets per type
%
% OUTPUT:
%   add[t] = extra pallets of type t to recommend
%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%

int: T;
set of int: TYPES = 1..T;

array[TYPES] of int: len;
array[TYPES] of int: wid;
array[TYPES] of int: hgt;

int: BUF;
int: free_len;

array[TYPES] of int: max_add;   % upper bounds per type

% Decision variables: how many extra of each type
array[TYPES] of var int: add;

% Bounds
constraint forall(t in TYPES)(
  0 <= add[t] /\ add[t] <= max_add[t]
);

% Capacity constraint along Y:
% Sum of (length + buffer) for each copy must fit in free_len
constraint
  sum(t in TYPES)(
    add[t] * (len[t] + BUF)
  ) <= free_len;

% Objective: maximize added volume (can tweak if needed)
var int: total_added_volume =
  sum(t in TYPES)(
    add[t] * len[t] * wid[t] * hgt[t]
  );

solve maximize total_added_volume;

output [
  "add = [",
  concat([
    show(add[t]) ++ (if t < T then ", " else "" endif)
    | t in TYPES
  ]),
  "];\n"
];