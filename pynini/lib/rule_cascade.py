# Copyright 2016-2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

# For general information on the Pynini grammar compilation library, see
# pynini.opengrm.org.
"""Rule cascade object for Pynini.

This module provides a class for applying rewrite rules (stored in a FAR) to
strings. It makes use of various functions (and a similar API) to the rewrite
library itself. Note that much of this functionality requires a semiring with
the path property.

See `rewrite.py` for more information about interpreting the rewrite functions.
"""

from typing import Iterable, List, Optional

import pynini
from pynini.lib import rewrite


class Error(Exception):
  """Errors specific to this module."""

  pass


class RuleCascade:
  """A rule cascade is a series of rules to be applied in order to a string.

  The caller must provide the path to a FAR file, and a set of rules before
  calling any other methods.
  """

  def __init__(self, far_path: str):
    self.far = pynini.Far(far_path, "r")
    self.rules = []

  def set_rules(self, rules: Iterable[str]) -> None:
    """Initializes a rule cascade.

    Args:
      rules: An iterable of strings naming rules in the input FAR.
    """
    self.rules.clear()
    for rule in rules:
      if self.far.find(rule):
        self.rules.append(self.far.get_fst().arcsort(sort_type="ilabel"))
      else:
        raise Error(f"Cannot find rule: {rule}")

  def _rewrite_lattice(
      self,
      string: pynini.FstLike,
      token_type: Optional[pynini.TokenType] = None) -> pynini.Fst:
    """Applies all rules to an input string.

    Args:
      string: Input string or FST.
      token_type: Optional input token type, or symbol table.

    Returns:
      The lattice of output strings.

    Raises:
      Error: No rules requested.
    """
    if not self.rules:
      raise Error("No rules requested")
    lattice = string
    for rule in self.rules:
      lattice = rewrite.rewrite_lattice(lattice, rule, token_type)
    else:
      if not isinstance(lattice, pynini.Fst):
        lattice = pynini.accep(lattice, token_type=token_type)
    return lattice

  # Rewrite functions.

  def matches(self,
              istring: pynini.FstLike,
              ostring: pynini.FstLike,
              input_token_type: Optional[pynini.TokenType] = None,
              output_token_type: Optional[pynini.TokenType] = None) -> bool:
    """Returns whether or not the rule cascade allows an input/output pair.

    Args:
      istring: Input string or FST.
      ostring: Output string or FST.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optional output token type, or symbol table.

    Returns:
      Whether the input-output pair is generated by the rule.
    """
    lattice = self._rewrite_lattice(istring, input_token_type)
    # TODO(kbg): Consider using `contextlib.nullcontext` here instead.
    if output_token_type is None:
      lattice = pynini.intersect(lattice, ostring, compose_filter="sequence")
    else:
      with pynini.default_token_type(output_token_type):
        lattice = pynini.intersect(lattice, ostring, compose_filter="sequence")
    return lattice.start() != pynini.NO_STATE_ID

  def rewrites(self,
               string: pynini.FstLike,
               input_token_type: Optional[pynini.TokenType] = None,
               output_token_type: Optional[pynini.TokenType] = None,
               state_multiplier: int = 4) -> List[str]:
    """Returns all rewrites.

    Args:
      string: Input string or FST.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optional output token type, or symbol table.
      state_multiplier: Max ratio for the number of states in the DFA lattice to
        the NFA lattice; if exceeded, a warning is logged.

    Returns:
      A tuple of output strings.
    """
    lattice = self._rewrite_lattice(string, input_token_type)
    lattice = rewrite.lattice_to_dfa(lattice, False, state_multiplier)
    return rewrite.lattice_to_strings(lattice, output_token_type)

  def top_rewrites(
      self,
      string: pynini.FstLike,
      nshortest: int,
      input_token_type: Optional[pynini.TokenType] = None,
      output_token_type: Optional[pynini.TokenType] = None) -> List[str]:
    """Returns the top n rewrites.

    Args:
      string: Input string or FST.
      nshortest: The maximum number of rewrites to return.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optionla output token type, or symbol table.

    Returns:
      A tuple of output strings.
    """
    lattice = self._rewrite_lattice(string, input_token_type)
    lattice = rewrite.lattice_to_nshortest(lattice, nshortest)
    return rewrite.lattice_to_strings(lattice, output_token_type)

  def top_rewrite(self,
                  string: pynini.FstLike,
                  input_token_type: Optional[pynini.TokenType] = None,
                  output_token_type: Optional[pynini.TokenType] = None) -> str:
    """Returns one top rewrite.

    Args:
      string: Input string or FST.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optionla output token type, or symbol table.

    Returns:
      The top string.
    """
    lattice = self._rewrite_lattice(string, input_token_type)
    return rewrite.lattice_to_top_string(lattice, output_token_type)

  def one_top_rewrite(self,
                      string: pynini.FstLike,
                      input_token_type: Optional[pynini.TokenType] = None,
                      output_token_type: Optional[pynini.TokenType] = None,
                      state_multiplier: int = 4) -> str:
    """Returns one top rewrite, unless there is a tie.

    Args:
      string: Input string or FST.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optional output token type, or symbol table.
      state_multiplier: Max ratio for the number of states in the DFA lattice to
        the NFA lattice; if exceeded, a warning is logged.

    Returns:
      The top string.
    """
    lattice = self._rewrite_lattice(string, input_token_type)
    lattice = rewrite.lattice_to_dfa(lattice, True, state_multiplier)
    return rewrite.lattice_to_one_top_string(lattice, output_token_type)

  def optimal_rewrites(self,
                       string: pynini.FstLike,
                       input_token_type: Optional[pynini.TokenType] = None,
                       output_token_type: Optional[pynini.TokenType] = None,
                       state_multiplier: int = 4) -> List[str]:
    """Returns all optimal rewrites.

    Args:
      string: Input string or FST.
      input_token_type: Optional input token type, or symbol table.
      output_token_type: Optional output token type, or symbol table.
      state_multiplier: Max ratio for the number of states in the DFA lattice to
        the NFA lattice; if exceeded, a warning is logged.

    Returns:
      A tuple of output strings.
    """
    lattice = self._rewrite_lattice(string, input_token_type)
    lattice = rewrite.lattice_to_dfa(lattice, True, state_multiplier)
    return rewrite.lattice_to_strings(lattice, output_token_type)

