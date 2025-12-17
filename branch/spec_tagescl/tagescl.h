#ifndef BRANCH_TAGESCL_H
#define BRANCH_TAGESCL_H

#include "modules.h"

#include "tagescl/tagescl.hpp"


struct ChampsimTageScl {
  using Impl = tagescl::Tage_SC_L<tagescl::CONFIG_64KB>;
  enum State {
    NONE,
    PREDICTED,
  };

  ChampsimTageScl(std::size_t max_inflight_branches)
      : impl(max_inflight_branches), id(0), state(NONE) {}

  Impl impl;
  std::uint64_t last_ip;
  std::uint32_t id;
  State state;
};


struct spec_tagescl : champsim::modules::branch_predictor
{
  using branch_predictor::branch_predictor;

  std::vector<ChampsimTageScl> predictors;

  void initialize_branch_predictor();
  bool predict_branch(uint64_t ip);
  void last_branch_result(uint64_t ip, uint64_t branch_target, bool taken, uint8_t branch_type);
};

#endif
