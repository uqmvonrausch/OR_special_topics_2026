import gurobipy as gp
import json
import visualise

from mine_site_classes import Shovel, Dump, Job, OperatingRules, TruckState

with open("./data/scenario_0.5.json") as data_file:
    data = json.load(data_file)

operating_rules = OperatingRules.from_data(data)

MINS_PER_HOUR = 60

S = [Shovel(s["id"], s["initial_trucks"]) for s in data["shovels"]]
D = [Dump(d["id"], d["initial_trucks"], d["desired_throughput"]) for d in data["dumps"]]
T = range(data["shift_duration_hours"] * MINS_PER_HOUR)

Jobs = {Job(s, d, TruckState.LOADED,   data["distance_matrix"][si][di], operating_rules)
        for si, s in enumerate(S) for di, d in enumerate(D)} | \
       {Job(d, s, TruckState.UNLOADED, data["distance_matrix"][si][di], operating_rules)
        for si, s in enumerate(S) for di, d in enumerate(D)}

m = gp.Model()

# 1 if job j is initiated at timestep t; ub=0 prevents jobs that would extend past the shift
X = {(j,t):
     m.addVar(vtype=gp.GRB.BINARY,
              ub=0 if t + j.duration > len(T) else 1,
              name=f"X_{j.id},{t}")
     for j in Jobs for t in T}

# Number of trucks waiting to load at shovel s at timestep t
Y = {(s,t):
     m.addVar(vtype=gp.GRB.INTEGER, name=f"Y_{s.site_id},{t}")
     for s in S for t in T}

# Number of trucks waiting to unload at dump s at timestep t
Z = {(d,t):
     m.addVar(vtype=gp.GRB.INTEGER, name=f"Z_{d.site_id},{t}")
     for d in D for t in T}

trucks_start_idle = {j:
                     m.addConstr(X[j,0] == 0)
                     for j in Jobs}

initial_trucks_at_shovels = {s:
                           m.addConstr(Y[s,0]==s.init_trucks)
                           for s in S}

initial_trucks_at_dumps = {d:
                           m.addConstr(Z[d,0]==d.init_trucks)
                           for d in D}

# Require minimum production at each dump
dump_production = {d:
                   m.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[j,t] for j in Jobs for t in T if j.destination == d)
                                              >= d.desired_throughput)
                   for d in D}

# Cannot begin loading within "loading_time_min" of another load operation starting
traffic_at_shovel = {(s,t):
                     m.addConstr(gp.quicksum(X[j,tt] for j in Jobs if j.source == s for tt in range(max(0,t-data["loading_time_min"])+1,t+1)) <= 1)
                     for s in S for t in T}

# # Cannot begin unloading within "unloading_time_min" of another unload operation starting
traffic_at_dump = {(d,t):
                     m.addConstr(gp.quicksum(X[j,tt] for j in Jobs if j.source == d for tt in range(max(0,t-data["unloading_time_min"])+1,t+1)) <= 1)
                     for d in D for t in T}

queueing_at_shovel = {(s,t):
                      m.addConstr(Y[s,t-1] + gp.quicksum(X[j,t-j.duration] for j in Jobs if j.destination == s and t - j.duration > 0) == 
                                  gp.quicksum(X[j,t] for j in Jobs if j.source == s) + Y[s,t])
                      for s in S for t in T if t > 0}

queueing_at_dump = {(d,t):
                      m.addConstr(Z[d,t-1] + gp.quicksum(X[j,t-j.duration] for j in Jobs if j.destination == d and t - j.duration > 0) == 
                                  gp.quicksum(X[j,t] for j in Jobs if j.source == d) + Z[d,t])
                      for d in D for t in T if t > 0}

# n_trucks_per_timestep = {t:
#                          m.addConstr(gp.quicksum(Y[s,t] for s in S) + gp.quicksum(Z[d,t] for d in D) + 
#                                      gp.quicksum(X[j,tt] for j in Jobs for tt in range(max(0,t-j.duration+1),t+1)) == data["n_trucks"])
#                          for t in T}

m.setObjective(
    gp.quicksum(data["revenue_per_ton"] * data["truck_capacity_tons"] * X[j,t] for j in Jobs if j.truck_state == TruckState.LOADED for t in T) #- 
    # gp.quicksum((j.distance / 1000) * X[j,t] * (data["cost_loaded_per_m"] + data["fixed_cost_loaded_per_m"]) for j in Jobs for t in T)
    , gp.GRB.MAXIMIZE)

m.optimize()

if m.Status == gp.GRB.OPTIMAL or m.Status == gp.GRB.SUBOPTIMAL:

    n_trucks = {t:round(sum(Y[s,t].x for s in S) + sum(Z[d,t].x for d in D) + sum(X[j,tt].x for j in Jobs for tt in range(max(0,t-j.duration+1),t+1))) for t in T}
    # print(n_trucks)
    # for j in Jobs:
    #     for t in T:
    #         if round(X[j,t].x) == 1:
    #             for min in range(0, j.duration):
    #                 if t+min <= len(T)-1:
    #                     n_trucks[t+min] += 1
    #                 else:
    #                     print(f"Job overflow for {j} starting at time {t}")
    #                     break
    print(n_trucks)    

    print("\n=== Truck Flow Results ===\n")

    # Arc flow totals: how many trucks traversed each arc over the full shift
    print("--- Arc Flow Totals ---")
    for j in Jobs:
        total = sum(round(X[j,t].x) for t in T)
        if total > 0:
            print(f"{j} : {total} truck(s)")

    # Timeline: for each minute, list jobs initiated at that timestep
    print("\n--- Flow Timeline (active initiations) ---")
    for t in T:
        active = [j for j in Jobs if round(X[j,t].x) == 1]
        if active:
            print(f"  t={t:4d}:", end="")
            for j in active:
                print(j, end="")
            print()
    # sol = visualise.extract(X, Y, Z, Jobs, S, D, T, data)
    # visualise.show(sol)
else:
    print(f"No feasible solution found (status {m.Status})")
