// Branch Agnostic Region Searching Algorithm

#include "barca.h"

#include <assert.h>
#include <list>
#include <map>
#include <math.h>
#include <stdio.h>
#include <string.h>
#include <string>
#include <unistd.h>
#include <cstdlib>
#include <iterator>

#include "cache.h"
#include "instruction.h"

using namespace std;

// this falls apart if block size isn't 64. I think.

#define BLOCK_SIZE      64
#define LOG2_BLOCK_SIZE 6

// need a region number that is unlikely to come up so we can initialize region numbers

#define INVALID_REGION 0xdeadbeef

// maximum number of blocks per region (currently we use 2)

#define MAX_BLOCKS_PER_REGION 16
#define LG_blocks_per_region  1

// to make the cache simulator smaller, we use only partial tag bits

#define CACHE_PARTIAL_TAG_BITS 24

char benchmark[1000]; // current benchmark name (from environment variable)

int cfg_repl = 0;

// parameters to the algorithm

int blocks_per_region       = 2,  // blocks per region
        real_depth          = 6,  // depth to search in the graph including traversing edges with outdegree 1
        dequeue_per_cycle   = 4,  // maximum number of prefetches to dequeue and issue per cycle
        inc_late            = 5,  // increment edge count by this much on a late prefetch
        inc_useful          = 3,  // increment edge count by this much on a useful prefetch
        dec_useless         = 2,  // decrement edge count by this much on a useless prefetch
        counter_width       = 18, // counter width
        depth               = 5,  // maximum depth to search the CFG, not including edges with outdegree 1
        would_be_nice_limit = 10, // maximum size of the "would be nice" list
        max_q_insertions    = 5,  // maximum number of candidates prefetches to add to the prefetch queue per search
        pf_queue_size       = 14, // size of the queue of prefetches (our queue, not ChampSim's)
        ras_size            = 64, // depth of the return address stack
        area_offset_bits    = 12, // number of bits in an area offset (for region address compression)
        recency_limit       = 5;  // size of queue of recently visited regions

// size of a region in bytes
int region_size = (BLOCK_SIZE * blocks_per_region);

// minimum probability to continue a search, per depth level

double mp[5] = {
        0.075,  // first level tuned on develop branch 3/30/2023
        0.001,  // second level
        0.0275, // third level
        0.007,  // fourth level
        0.0,    // not reached
};

struct cfg_edge;

// this struct holds stuff we need to make and train a single prefetch

uint64_t global_time = 0;

struct prefetch_info
{
                cfg_edge* b;       // the edge responsible for triggering this prefetch
                uint64_t  pf_addr; // the address of the prefetch
                double    d;       // the probability computed by the search for this prefetch
                int       depth;   // the depth where this prefetch was found

                // we need to be able to sort these by probabilities to schedule the prefetches.
                // so we define < to sort in descending order of probability

                prefetch_info(void)
                {
                        // explicitly initialize everything
                        b       = NULL;
                        pf_addr = 0;
                        d       = 0.0;
                        depth   = 0;
                }

                bool operator<(const prefetch_info& other) const
                {
                        return d > other.d;
                }
};

list<prefetch_info>

        // a queue of recently generated prefetches to issue

        prefetch_queue,

        // a queue of lower-probability prefetches we will issue if there is some idle time

        would_be_nice_queue;

// the return address stack, checked when we might follow an "is-return" edge

list<uint64_t> ras;

// we simulate a "shadow cache" to mirror the real L1I cache. this is one block of the simulated cache

struct cache_block
{
                uint64_t  tag;         // the (partial) tag
                bool      valid;       // valid bit
                bool      prefetched;  // this block was prefetched but not used yet
                int       lruposition; // lru replacement information (3 bits)
                cfg_edge* edge;        // the edge responsible for this prefetch (if any)

                // constructor

                cache_block(void)
                {
                        // initialize all fields. we will initialize LRU bits in a loop later

                        tag         = 0;
                        valid       = false;
                        prefetched  = false;
                        lruposition = 0;
                        edge        = NULL;
                }
};

// we compress region numbers using an area map, where there are a number of areas
// representing upper bits of region numbers. a region is 64 - LOG2_BLOCK_SIZE - LG_blocks_per_region bits.

#define LG_NUM_AREAS 7
#define REGION_BITS  (64 - LOG2_BLOCK_SIZE - LG_blocks_per_region)
#define NUM_AREAS    (1ull << LG_NUM_AREAS)

// with 2 blocks per region, and 12 bits of area offset bits, we get 64 * 2 * 4096 = 512KB of space per region. should be enough!

#define AREA_UPPER_BITS (REGION_BITS - area_offset_bits)
#define UNUSED_AREA     (INVALID_REGION & ((1ull << AREA_UPPER_BITS) - 1))

uint64_t area_map[NUM_AREAS];

// this struct contains the compressed representation of a CFG node, i.e. the address of a region

struct node
{
                uint64_t area, offset;

                // make this back into an address

                node(void)
                {
                        area   = 0;
                        offset = 0;
                }

                uint64_t expand(void)
                {
                        uint64_t x = (area_map[area] << area_offset_bits) | offset;
                        return x;
                }

                // need to be able to compare these

                bool operator==(node& other)
                {
                        return (other.area == area) && (other.offset == offset);
                }

                bool operator!=(node& other)
                {
                        return !(other == *this);
                }

                // need to be able to sort these

                bool operator<(node& other)
                {
                        return expand() < other.expand();
                }

                bool operator>(node& other)
                {
                        return expand() > other.expand();
                }
};

// return a node that compresses an address into the compact area/offset representation

node compress(uint64_t x)
{
        // this points to the next area map entry to replace on a miss

        static int replacement_index = NUM_AREAS / 2;

        // compute the upper bits of the region address

        uint64_t upper_bits = x >> area_offset_bits;
        assert(upper_bits < (1ull << AREA_UPPER_BITS));
        unsigned int r;

        // search for the corresponding area map entry

        for(r = 0; r < NUM_AREAS; r++)
                if(area_map[r] == upper_bits)
                        break;

        // if we miss in the area map...
        if(r == NUM_AREAS)
        {
                // get an unused area

                for(r = 0; r < NUM_AREAS; r++)
                        if(area_map[r] == UNUSED_AREA)
                                break;

                // no unused area? replace the next one in sequence and bump the index. but this never happens.

                if(r == NUM_AREAS)
                        r = replacement_index++ % NUM_AREAS;

                // place the new area into the map

                area_map[r] = upper_bits;
        }

        // prepare a compressed node to return

        node n;

        // the area number is the one we found or replaced in the map

        n.area = r;

        // get the offset bits from the region address

        n.offset = x & ((1ull << area_offset_bits) - 1);

        // done

        return n;
}

// we keep a control flow graph that resembles a branch target buffer. this struct represents an edge
// in an adjacency list representation, where the lists are laid out as rows in a tagged cache-like structure
// where the set index is derived from the source region and the targets are all in the same set, possibly
// sharing the set with a number of sources. the nodes in the graph are multi-block regions

struct cfg_edge
{
                // number of times this edge has been traversed. the count is also tweaked on useless, useful, and late prefetches

                int      count;
                node     tag;                                    // tag of the source region
                node     target;                                 // block number of the target region
                bool     spatial_pattern[MAX_BLOCKS_PER_REGION]; // bitmap giving which blocks within a region were actually used
                bool     is_return;                              // indicates this edge's source was a return so it should be searched specially
                uint64_t timestamp;

                // constructor

                cfg_edge(void)
                {
                        // initialize fields

                        count     = 0;
                        is_return = false;
                        memset(spatial_pattern, 0, blocks_per_region);
                        timestamp = 0;
                }
};

// define the number of sets and associativity of the CFG; 256 sets, 64-way set-associative

#define CFG_LG_ASSOC 6
#define CFG_LG_SETS  8

#define CFG_ASSOC (1 << CFG_LG_ASSOC)
#define CFG_SETS  (1 << CFG_LG_SETS)

int cfg_sets = CFG_SETS;

cfg_edge CFG[CFG_SETS][CFG_ASSOC];

// this function initializes the CFG

void init_cfg(void)
{
        // initialize the area map to all unused

        for(unsigned int i = 0; i < NUM_AREAS; i++) area_map[i] = UNUSED_AREA;

        // get the compressed representation of region 0, indicating an unused edge

        node zero = compress(0);

        // initialize all nodes to unused, all counts to 0

        for(int i = 0; i < cfg_sets; i++)
                for(int j = 0; j < CFG_ASSOC; j++)
                {
                        CFG[i][j].tag   = zero;
                        CFG[i][j].count = 0;
                }
}

// increment an edge counter, halving all the edges in the CFG if a counter reaches the maximum value

void countup(cfg_edge* b)
{
        if(b->count >= ((1 << counter_width) - 1))
                for(int i = 0; i < cfg_sets; i++)
                        for(int j = 0; j < CFG_ASSOC; j++) CFG[i][j].count /= 2;
        b->count++;
        b->timestamp = global_time++;
}

// insert an edge from source to target into the CFG. the source is a region number

cfg_edge* insert_cfg(uint64_t source, uint64_t target)
{
        // no reflexive edges

        if(source == target)
                return NULL;

        // convert 64 bit target to a 19-bit node representation

        node n = compress(target);

        // figure out the set number in the CFG; source is already a region address

        unsigned int set = source % cfg_sets;

        // the tag for this edge is the compressed source address

        node tag = compress(source);

        // the lower bits of the tag offset are the same as the set index; we don't need to store those bits

        assert(tag.offset % cfg_sets == set);

        // get a pointer to this CFG set

        cfg_edge* S = &CFG[set][0];

        // see if the target is already there

        for(int i = 0; i < CFG_ASSOC; i++)
        {
                if(S[i].tag == tag)
                {
                        if(S[i].target == n)
                        {
                                // one more instance of this edge; count up

                                countup(&S[i]);

                                // return pointer to the accessed block

                                return &S[i];
                        }
                }
        }

        // missed, so the edge is not there. find a replacement with least-frequently used policy based on count

        int r;

        if(cfg_repl == 2)
        {
                // get the LRU block
                int minr = 0;
                for(r = 0; r < CFG_ASSOC; r++)
                        if(S[r].timestamp < S[minr].timestamp)
                                minr = r;
                r = minr;
                assert(r != CFG_ASSOC);
        }
        else
        {
                // get the LFU block

                int minr = 0;
                for(r = 0; r < CFG_ASSOC; r++)
                        if(S[r].count < S[minr].count)
                                minr = r;
                r = minr;
                assert(r != CFG_ASSOC);
        }

        // place the edge into this invalid or replaced block

        S[r].target = n;
        S[r].tag    = tag;

        // bugfix
        if(cfg_repl >= 1)
                S[r].count = 0;

        // we don't know if it's a return yet, but if we're invoked from the return-handling code it'll put in the flag

        S[r].is_return = false;

        // count up for the first time

        countup(&S[r]);

        // zero out the spatial pattern since we don't know the region offset that generated this insertion;
        // someone will fill in the right bits later

        memset(S[r].spatial_pattern, 0, sizeof(S[r].spatial_pattern));

        // return pointer to the new edge

        return &S[r];
}

// search the CFG for all targets reachable in one hop from this source

list<cfg_edge*> search_cfg(uint64_t source)
{
        // this list can be thought of as part of the search_results map where the items are eventually copied

        list<cfg_edge*> L;

        // find the set containing the edges for this node

        int set = source % cfg_sets;

        // get the compressed representation so we can match this source with targets in this set

        node tag = compress(source);

        // get a pointer to this set

        cfg_edge* S = &CFG[set][0];

        // go through the set looking for targets that match this source

        for(int i = 0; i < CFG_ASSOC; i++)
        {
                // a match?

                if(S[i].tag == tag)
                {
                        // if this edge is from a return, only include it in the search result if the
                        // target is currently on the return address stack

                        bool doit = false;
                        if(S[i].is_return)
                        {
                                // get the uncompressed representation of the target

                                uint64_t target_region = S[i].target.expand();

                                // search the upper bits of return address stack entries for this target

                                for(auto p = ras.begin(); p != ras.end(); p++)
                                {
                                        uint64_t return_region = *p / region_size;
                                        if(return_region == target_region)
                                        {
                                                // did we find it? then it's ok to include this edge in the search

                                                doit = true;
                                                break;
                                        }
                                }
                        }
                        else

                                // not a return? then it's ok to include this edge in the search results

                                doit = true;

                        // this edge goes into the search results

                        if(doit)
                                L.push_back(&S[i]);
                }
        }

        // return the list of search results to become part of the search_results list

        return L;
}

// simulated instruction cache, or "shadow cache"

int global_set = 0, global_way = 0;

#define L1I_SET global_set
#define L1I_WAY global_way

// safe assumptions for an instruction cache

#define MAX_SET 8192
#define MAX_WAY 64

cache_block shadow_cache[MAX_SET][MAX_WAY];

// types of operations supported on the simulated cache

#define ACCESS_DEMAND   1 // a demand fetch
#define ACCESS_PREFETCH 2 // a prefetch
#define ACCESS_PROBE    3 // just looking for information, not changing anything

// move a simulated cache block to the MRU position

void move_to_mru(cache_block* S, int set, int r)
{
        int position = S[r].lruposition;
        for(int i = 0; i < L1I_WAY; i++)
                if(S[i].lruposition < position)
                        S[i].lruposition++;
        S[r].lruposition = 0;
}

// initialize the simulated cache

void init_cache(void)
{
        for(int set = 0; set < L1I_SET; set++)
        {
                cache_block* S = &shadow_cache[set][0];
                for(int way = 0; way < L1I_WAY; way++)
                {
                        // distinct LRU positions

                        S[way].lruposition = way;
                        S[way].valid       = false;
                        S[way].tag         = 0xdeadbeef;
                }
        }
}

// access the shadow cache, returning information through pointers

void access_cache(uint64_t   addr,               // the virtual address of the access
                  bool*      hit,                // return true if this is a hit, false otherwise
                  bool*      prefetch_hit,       // return true if this is a not-yet accessed prefetch hit
                  uint64_t   real_victim = 0,    // the real victim from the cache fill, as opposed to our idea of the victim
                  cfg_edge*  edge        = NULL, // the edge responsible for this prefetch access
                  cfg_edge** get_edge    = NULL, // return the edge responsible for this prefetch filled earlier
                  int        access_type = ACCESS_DEMAND)
{ // the access type

        // figure out the block address, set index, and tag

        uint64_t block_addr = addr / BLOCK_SIZE;
        int      set        = block_addr % L1I_SET;
        uint64_t tag        = (block_addr / L1I_SET) & ((1ull << CACHE_PARTIAL_TAG_BITS) - 1);

        // get a pointer to this set

        cache_block* S = &shadow_cache[set][0];

        // initialize the edge to be returned to NULL, maybe fill it with something else later

        if(get_edge)
                *get_edge = NULL;

        // if we have a victim address, use that one for replacement by invalidating it

        if(real_victim)
        {
                // make sure this victim is actually in this set (trust ChampSim to start using weird hash functions)

                int rvset = (real_victim / BLOCK_SIZE) % L1I_SET;
                assert(rvset == set);

                // go through each way looking for this victim

                for(int i = 0; i < L1I_WAY; i++)
                {
                        // figure out the (partial) address of this block

                        uint64_t my_addr = ((S[i].tag * L1I_SET) | set) * BLOCK_SIZE;

                        // prepare a mask to allow comparing the shorter addresses

                        uint64_t mask = ((1ull << CACHE_PARTIAL_TAG_BITS) * L1I_SET * BLOCK_SIZE) - 1;

                        // do the addresses match in the lower bits?

                        if((my_addr & mask) == (real_victim & mask))
                        {
                                // yes? ok, invalidate this block so it will be replaced instead of the LRU block

                                S[i].valid = false;

                                // why do we do this?
                                // if (get_edge) *get_edge = S[i].edge;
                                break;
                        }
                }
        }

        // search this set for the block

        for(int i = 0; i < L1I_WAY; i++)
        {
                // can we match a tag for this valid block?

                if(S[i].valid)
                        if(S[i].tag == tag)
                        {
                                // a hit! return the fact that it was a hit.

                                if(hit)
                                        *hit = true;

                                // return whether this is an as-yet unaccessed prefetch

                                if(prefetch_hit)
                                        *prefetch_hit = S[i].prefetched;

                                // is this the first demand access to this prefetched block?

                                if((access_type == ACCESS_DEMAND) && S[i].prefetched)
                                {
                                        // good, we hit something we prefetched! this is a useful prefetch. marked it as
                                        // no longer prefetch since it is now found in the demand stream

                                        S[i].prefetched = false;

                                        // strengthen the counter for this edge

                                        if(S[i].edge)
                                                for(int k = 0; k < inc_useful; k++) countup(S[i].edge);
                                }

                                // if this is a demand or prefetch access, move it to the MRU position

                                if(access_type != ACCESS_PROBE)
                                        move_to_mru(&S[0], set, i);

                                // fill the edge field if available

                                if(edge)
                                        S[i].edge = edge;

                                // return the edge field if requested

                                if(get_edge)
                                        *get_edge = S[i].edge;

                                // done!

                                return;
                        }
        }

        // a miss!

        // return the bad news

        if(hit)
                *hit = false;
        if(prefetch_hit)
                *prefetch_hit = false;

        // place the block. first look for an invalid block

        int r;
        for(r = 0; r < L1I_WAY; r++)
                if(S[r].valid == false)
                        break;

        // no invalid block? get the LRU block

        if(r == L1I_WAY)
        {
                r = 0;
                for(int i = 0; i < L1I_WAY; i++)
                        if(S[i].lruposition == L1I_WAY - 1)
                                r = i;
                assert(r != L1I_WAY);
        }

        // if this were a probe, don't do anything else (why return here? at some point we might want to
        // know the LRU position of this access, so we could return it for a predictor or something)

        if(access_type == ACCESS_PROBE)
                return;

        // is this an as-yet unaccessed block?

        if(S[r].prefetched)
        {
                // we are evicting this prefetched block before ever accessing it!
                // weaken the counter for this useless prefetch edge

                if(S[r].edge)
                {
                        S[r].edge->count -= dec_useless;
                        if(S[r].edge->count < 0)
                                S[r].edge->count = 0;
                }
        }

        // place this block in the MRU position

        move_to_mru(&S[0], set, r);

        // mark whether this insertion is a prefetch

        S[r].prefetched = (access_type == ACCESS_PREFETCH);

        // set the metadata

        S[r].tag   = tag;
        S[r].valid = true;

        // fill in the edge responsible for this prefetch if provided

        if(edge)
                S[r].edge = edge;
}

// this is the value for a map of prefetch candidates; we use the
// probability and depth to order the resulting list of candidates

struct sigpair
{
                double prob;
                int    depth;

                sigpair(void)
                {
                        prob  = 0.0;
                        depth = 0;
                }
};

// there are some lists that need to be limited in size. 56 works.

#define MAX_LIST_SIZE 56

// depth-limited recursive depth first search of the control graph from a source node

void depth_first_search(cfg_edge*                node,   // the target if this node is the source for this search
                        int                      d,      // the depth of this search, not including edges along the path with outdegree 1
                        int                      real_d, // the real depth of this search, including outdegree one edges
                        map<cfg_edge*, sigpair>& S,      // search results are returned in this map
                        double                   piprod)
{ // the cumulative probability down this path

        // don't search too deeply

        if(d <= depth && real_d <= real_depth)
        {
                // get the block address from this region

                uint64_t block_addr = node->target.expand() * blocks_per_region;

                // for each block in the region, see if it is not in the cache

                for(int i = 0; i < blocks_per_region; i++)
                {
                        // ignore blocks that have never been accessed according to the spatial pattern

                        if(node->spatial_pattern[i] == false)
                                continue;

                        // compute the address of this block

                        uint64_t addr = (block_addr + i) * BLOCK_SIZE;

                        // see if we hit this block in the cache

                        bool hit;
                        access_cache(addr, &hit, NULL, 0, NULL, NULL, ACCESS_PROBE);

                        // if this block is not in the cache, record it in the map of search results

                        if(!hit)
                        {
                                // don't let the map get too big

                                if(S.size() < MAX_LIST_SIZE)
                                {
                                        auto p = S.find(node);

                                        // record its probability and depth in the map

                                        if(p == S.end())
                                        {
                                                S[node].depth = d;
                                                S[node].prob  = piprod;
                                        }
                                        // we're done; one block in the region is enough to trigger a prefetch
                                        break;
                                }
                        }
                }

                // recursively search the next level

                // get the list of matching targets reachable in one hop from this source

                list<cfg_edge*> L = search_cfg(node->target.expand());

                // we will compute the probabilities of each target based on their count divided by the total count

                int total = 0;
                for(auto p = L.begin(); p != L.end(); p++) total += (*p)->count;
                if(total == 0)
                        total = 1;

                // we only increase the depth counter if this source had more than one target

                int next_d = d;
                if(L.size() > 1)
                        next_d++;

                // for each target beyond a minimum probability for this depth, search it

                for(auto p = L.begin(); p != L.end(); p++)
                {
                        // the probability of this target is the cumulative running probability plus its
                        // fraction of the total for this list of targets

                        double myprob = piprod * ((*p)->count / (double)total);
                        if(myprob >= mp[d])
                                depth_first_search(*p, next_d, real_d + 1, S, myprob);
                }
        }
}

// remember the last region we accessed so we can connect it to the next region and keep track of the current edge

uint64_t  last_region  = INVALID_REGION;
cfg_edge* current_edge = NULL;

// queue of recently searched regions we don't want to search again soon

list<uint64_t> recently_searched;

// this function is called by generate_prefetch_candidates to build the CFG and possibly initiate a search for
// prefetch candidates. it returns a list of prefetch candidates

list<prefetch_info> demand_fetch(uint64_t fetch_addr)
{
        map<uint64_t, bool> distinct_candidates;
        list<prefetch_info> prefetch_candidates;

        // what region is it in?

        uint64_t region = (fetch_addr / region_size);

        // did we enter a new region? then let's add this edge to the CFG and try to do some prefetching

        if(region != last_region)
        {
                if(last_region != INVALID_REGION)
                {
                        // look up this edge so we can accumulate region offset bits into it
                        current_edge = insert_cfg(last_region, region);
                        assert(current_edge);
                }
                last_region = region;

                // see if this region was recently searched; if so, this search is probably redundant so we'll
                // just return an empty list

                for(auto p = recently_searched.begin(); p != recently_searched.end(); p++)
                        if(*p == region)
                                return prefetch_candidates;

                // put this region onto the tail of the queue of recently searched regions and dequeue the head

                while(recently_searched.size() >= (unsigned int)recency_limit) recently_searched.pop_front();
                recently_searched.push_back(region);

                // find the set of non-cached regions at most 'depth' hops away in the CFG

                map<cfg_edge*, sigpair> search_results;

                // search from the current edge, at depth 0, "real" depth 0, inserting results into 'search_results',
                // and starting off with cumulative probability 1.0

                if(current_edge)
                        depth_first_search(current_edge, 0, 0, search_results, 1.0);

                // take the unordered search results and schedule them by probability into a list of regions to prefetch

                list<prefetch_info> frontier;
                for(auto p = search_results.begin(); p != search_results.end(); p++)
                {
                        prefetch_info b;
                        b.b     = (*p).first;
                        b.d     = (*p).second.prob;
                        b.depth = (*p).second.depth;
                        if(frontier.size() < MAX_LIST_SIZE)
                                frontier.push_back(b);
                }
                frontier.sort();

                // go through the list making prefetch addresses out of the regions, respecting the spatial patterns

                for(auto p = frontier.begin(); p != frontier.end(); p++)
                {
                        // this CFG edge's target is the candidate prefetch region

                        cfg_edge* c = (*p).b;

                        // get the uncompressed representation so we can twiddle the bits

                        uint64_t prefetch_region = c->target.expand();

                        // for each block in the region, check the spatial pattern

                        for(int i = 0; i < blocks_per_region; i++)
                                if(c->spatial_pattern[i])
                                {
                                        // this block has been seen before; get the block address for this prefetch candidate

                                        uint64_t addr = ((prefetch_region * blocks_per_region) + i) * BLOCK_SIZE;

                                        // make sure the candidates are distinct (we could have duplicates if the depth-first
                                        // search reached the same target on two different paths)

                                        if(!distinct_candidates[addr])
                                        {
                                                prefetch_info b;
                                                b.b                       = c;
                                                b.pf_addr                 = addr;
                                                b.depth                   = (*p).depth;
                                                b.d                       = (*p).d;
                                                distinct_candidates[addr] = true;

                                                // put a new prefetch candidate onto the list

                                                prefetch_candidates.push_back(b);
                                        }
                                }
                }
        }

        // update the spatial pattern based on demand-accessing this block

        if(current_edge)
        {
                uint64_t block_addr                                           = fetch_addr / BLOCK_SIZE;
                current_edge->spatial_pattern[block_addr % blocks_per_region] = true;
        }

        // done!

        return prefetch_candidates;
}

// initialize structures

void barca::prefetcher_initialize()
{
        printf("PQ size is %zu\n", intern_->PQ_SIZE);
        char* s = getenv("DEPTH");
        if(s)
        {
                sscanf(s, "%d", &depth);
                printf("DEPTH=%d\n", depth);
        }
        s = getenv("REAL_DEPTH");
        if(s)
        {
                sscanf(s, "%d", &real_depth);
                printf("REAL_DEPTH=%d\n", real_depth);
        }
        global_set = static_cast<int>(intern_->NUM_SET);
        global_way = static_cast<int>(intern_->NUM_WAY);
        s          = getenv("MP0");
        if(s)
        {
                sscanf(s, "%lf", &mp[0]);
                printf("MP[0]=%f\n", mp[0]);
        }
        s = getenv("CFG_SETS");
        if(s)
        {
                sscanf(s, "%d", &cfg_sets);
                printf("CFG_SETS=%d\n", cfg_sets);
        }
        s = getenv("CFG_REPL");
        if(s)
        {
                sscanf(s, "%d", &cfg_repl);
                printf("CFG_REPL=%d\n", cfg_repl);
        }
        init_cache();
        init_cfg();
}

void generate_prefetch_candidates(uint64_t addr);

// what to do when we get a branch

void barca::prefetcher_branch_operate(champsim::address ip, uint8_t branch_type, champsim::address branch_target)
{
        const uint64_t ip_val     = ip.to<uint64_t>();
        const uint64_t target_val = branch_target.to<uint64_t>();

        // if this is a call, push the return address on the return address stack

        if(branch_type == BRANCH_DIRECT_CALL || branch_type == BRANCH_INDIRECT_CALL)
        {
                // PC + 4 is a good estimate of the return address, especially on ARM but not bad on x86-64.

                if(ras.size() < (unsigned int)ras_size)
                        ras.push_front(ip_val + 4);
        }

        // if this is a return, we'll do some stuff

        if(branch_type == BRANCH_RETURN)
        {
                // turns out generating prefetch candidates from here can also help. (we access the cache here because
                // frickin' ChampSim seems to call this function and the cache operate function out of order, probably
                // because of all those prefetches we're issuing)

                access_cache(ip_val, NULL, NULL, 0, NULL, NULL, ACCESS_DEMAND);
                generate_prefetch_candidates(ip_val);

                // the branch target can be 0 because the conditional branch predictor can incorrectly predict the return
                // as not taken, in which case we're boned because there's no way to match up demand fetches and branch
                // addresses. but it's OK because the branch predictor is pretty accurate and we'll eventually get the
                // right target

                if(target_val != 0)
                {
                        // make this edge in the CFG and mark it as an "is-return" edge

                        uint64_t  source_region = ip_val / region_size;
                        uint64_t  target_region = target_val / region_size;
                        cfg_edge* b             = insert_cfg(source_region, target_region);
                        if(b)
                                b->is_return = true;
                }

                // pop the return address stack

                if(ras.size())
                        ras.pop_front();
        }
}

// generate prefetch candidates and put them into our prefetch queue

void generate_prefetch_candidates(uint64_t addr)
{
        // get a list of prefetch candidates by doing the depth first search etc.

        list<prefetch_info> L = demand_fetch(addr);

        // do up to max_q_insertions many insertions into the prefetch queue,
        // then put the rest into the "would be nice" queue

        int z = 0;

        // traverse the list of prefetch candidates we got from the search

        for(auto p = L.begin(); p != L.end(); p++, z++)
        {
                // make a prefetch_info struct from this item to put into the queue

                prefetch_info n;
                uint64_t      pf_addr = (*p).pf_addr;
                n.pf_addr             = pf_addr;
                n.d                   = (*p).d;
                n.depth               = (*p).depth;
                n.b                   = (*p).b;

                // if we haven't inserted too many, try to stick this candidate into the queue

                if(z < max_q_insertions)
                {
                        // if the queue has space, just stick it in there

                        if(prefetch_queue.size() < (unsigned int)pf_queue_size)
                        {
                                prefetch_queue.push_back(n);
                        }
                        else
                        {
                                // the queue is full. is there something lower priority in it we could replace?
                                // find the minimum priority thing in the queue
                                auto r = prefetch_queue.begin();
                                for(auto q = prefetch_queue.begin(); q != prefetch_queue.end(); q++)
                                {
                                        // (note the < operator for prefetch_info is actually > so we can sort in descending order)
                                        if(*r < *q)
                                        {
                                                r = q;
                                        }
                                }
                                // if the minimum is less than the probability of the current proposed prefetch, replace it
                                if(n < *r)
                                        *r = n;
                        }
                }
                else
                {
                        // if we have already put max_q_insertions many candidates into the queue, start filling the
                        // "would be nice" queue

                        if(would_be_nice_queue.size() < (unsigned int)would_be_nice_limit)
                                would_be_nice_queue.push_back(n);
                }
        }
}

// this is called whenever there's an access to the i-cache

// void CACHE::prefetcher_cache_operate(uint64_t addr, uint8_t cache_hit, uint8_t prefetch_hit) {
// prefetcher/ip_stride/ip_stride.cc:uint32_t CACHE::prefetcher_cache_operate(uint64_t addr, uint64_t ip, uint8_t cache_hit, uint8_t type, uint32_t metadata_in)

// void CACHE::prefetcher_cache_operate(uint64_t addr, uint8_t cache_hit, uint8_t prefetch_hit) {
uint32_t barca::prefetcher_cache_operate(champsim::address addr, champsim::address ip, uint8_t cache_hit, bool useful_prefetch, access_type type,
                                         uint32_t metadata_in)
{
        (void)ip;
        (void)useful_prefetch;
        (void)type;

        const uint64_t addr_val = addr.to<uint64_t>();

        // see if the shadow cache and real cache agree on whether this is a hit. if not, it could be a late prefetch.

        cfg_edge* edge;
        bool      hit, pre;
        access_cache(addr_val, &hit, &pre, 0, NULL, &edge, ACCESS_PROBE);
        if(!cache_hit && pre)
        {
                // we have a late prefetch. strength this connection to bump it up in the queue next time.

                if(edge)
                        for(int i = 0; i < inc_late; i++) countup(edge);
        }

        // get rid of this demand fetch from our prefetch queue

        for(auto p = prefetch_queue.begin(); p != prefetch_queue.end(); p++)
                if((addr_val & ~(BLOCK_SIZE - 1)) == (*p).pf_addr)
                        p = prefetch_queue.erase(p);

        // make this demand access to the shadow cache

        access_cache(addr_val, NULL, NULL, 0, NULL, NULL, ACCESS_DEMAND);

        // fill our queue with prefetch candidates triggered from this access

        generate_prefetch_candidates(addr_val);
        return metadata_in;
}

// this is called on "every" cycle except when it's not

void barca::prefetcher_cycle_operate()
{
        // issue up to dequeue_per_cycle many prefetches on this cycle

        auto pq_occ_vec  = intern_->get_pq_occupancy();
        auto pq_size_vec = intern_->get_pq_size();
        auto pq_occ      = pq_occ_vec.empty() ? 0U : pq_occ_vec.back();
        auto pq_cap      = pq_size_vec.empty() ? intern_->PQ_SIZE : pq_size_vec.back();

        for(int i = 0; i < dequeue_per_cycle; i++)
        {
                // doesn't do any good to issue prefetches if the queue is full

                if(pq_occ < pq_cap)
                {
                        prefetch_info p;
                        if(prefetch_queue.size())
                        {
                                // dequeue a prefetch from our prefetch queue, if it's not empty

                                p = prefetch_queue.front();
                                prefetch_queue.pop_front();
                        }
                        else if((pq_occ == 0) && would_be_nice_queue.size())
                        {
                                // if ChampSim's prefetch queue is empty, issue one of those "would be nice" prefetches

                                p = would_be_nice_queue.front();
                                would_be_nice_queue.pop_front();
                        }
                        else
                                return;

                        // do the prefetch

                        const bool issued = prefetch_line(champsim::address{p.pf_addr}, true, 0);

                        // update the shadow cache with this prefetch
                        if(issued)
                        {
                                pq_occ++;

                                access_cache(p.pf_addr, NULL, NULL, 0, p.b, NULL, ACCESS_PREFETCH);
                        }
                }
        }
}

// this is never called anyway

void barca::prefetcher_final_stats() {}

// this is called when ChampSim gets around to filling the cache with data from the memory hierarchy

uint32_t barca::prefetcher_cache_fill(champsim::address addr, long set, long way, bool prefetch, champsim::address evicted_addr,
                                      uint32_t metadata_in)
{
        (void)set;
        (void)way;

        const uint64_t addr_val    = addr.to<uint64_t>();
        const uint64_t evict_value = evicted_addr.to<uint64_t>();

        if(!prefetch)
        {
                // if this isn't a prefetch, fill the shadow cache and search for more prefetch candidates

                access_cache(addr_val, NULL, NULL, evict_value, NULL, NULL, ACCESS_DEMAND);
                generate_prefetch_candidates(addr_val);
        }
        else
        {
                // if it is a prefetch, just fill the shadow cache

                access_cache(addr_val, NULL, NULL, evict_value, NULL, NULL, ACCESS_PREFETCH);
        }
        return metadata_in;
}
