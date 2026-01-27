#ifndef _MPP_BRANCH_H_
#define _MPP_BRANCH_H_

#include <stdint.h>
// this class contains information that is kept between prediction and update
// the only thing it has here is the prediction.  it should be subclassed to hold
// other data e.g. indices in tables, branch PC, etc.

class mpp_branch_update {
	bool _prediction;
public:
	unsigned int address;
	int confidence;

	mpp_branch_update (void) { }

	// set the prediction for this branch

	void prediction (bool p) {
		_prediction = p;
	}

	// return the prediction for this branch

	bool prediction (void) {
		return _prediction;
	}
};

// this class represents a branch predictor

class mpp_branch_predictor {
public:
	mpp_branch_predictor (void) { }

	// the first parameter is the branch address
	// the second parameter is true if the branch was ever taken
	// the third parameter is true if the branch was ever not taken
	// the return value is a pointer to a branch_update object that gives
	// the prediction and presumably contains information needed to
	// update the predictor

	virtual mpp_branch_update *lookup (unsigned int pc, uint64_t dynamic_id = 0, unsigned int* global_tage_pred = NULL, unsigned int* global_tage_conf = NULL) = 0;

	virtual void spec_update (mpp_branch_update *p, uint64_t target, bool taken, bool pred, int type, bool filtered, uint64_t dynamic_id = 0) { }

	// the first parameter is the branch info returned by the corresponding predict
	// the second parameter is the outcome of the branch

	virtual void update (mpp_branch_update *p, unsigned int target, bool taken, int type = 0, uint64_t dynamic_id = 0) { }
	virtual void update (mpp_branch_update *p, unsigned int target, bool taken, int type, bool do_train, bool filtered, uint64_t dynamic_id = 0) { }

	// if this returns false, then we will do lookup even for always/never taken branches

	virtual bool filter_always_never (void) { return true; }

	virtual void nonconditional_branch (unsigned int pc, unsigned int target, int type) { }

	virtual const char *name (bool) { return ""; }

	virtual ~mpp_branch_predictor (void) { }
};

#endif // _MPP_BRANCH_H_
