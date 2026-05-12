import gurobipy as gp
import json
import math

with open("./data/scenario_1.json") as data_file:
    data = json.load(data_file)

MINS_PER_HOUR = 60

SOURCE = 0
DUMP = 1
DEST = 2

NULL_JOB = (-1,-1,-1)

S = range(len(data["shovels"]))
D = range(len(data["dumps"]))
T = range(data["n_trucks"])    

def calc_job_duration(start_shovel_idx: int, dump_idx: int, end_shovel_idx: int):

    if (start_shovel_idx, dump_idx, end_shovel_idx) == NULL_JOB:
        return 0
    
    loaded_distance_m = data["distance_matrix"][start_shovel_idx][dump_idx]
    loaded_drive_time_min = (loaded_distance_m / data["speed_loaded_kph"]) * MINS_PER_HOUR / 1000

    unloaded_distance_m = data["distance_matrix"][end_shovel_idx][dump_idx]
    unloaded_drive_time_min = (unloaded_distance_m / data["speed_unloaded_kph"]) * MINS_PER_HOUR / 1000

    return data["loading_time_min"] + loaded_drive_time_min + \
        data["unloading_time_min"] + unloaded_drive_time_min

Jobs = {(s,d,ss) : calc_job_duration(s, d, ss)
        for s in S for d in D for ss in S}

K = range(math.ceil(data["shift_duration_hours"] * MINS_PER_HOUR / min(Jobs.values())))

Jobs[NULL_JOB] = 0

m = gp.Model()

X = {(j,k,t):
     m.addVar(vtype=gp.GRB.BINARY)     
     for j in Jobs for k in K for t in T}

one_job_per_slot = {(k,t):
                    m.addConstr(gp.quicksum(X[j,k,t] for j in Jobs) <= 1)
                    for k in K for t in T}

dump_capacity = {d:
                   m.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[j,k,t] for j in Jobs for k in K for t in T if j[DUMP] == d)
                                              <= data["dumps"][d]["processing_capacity"])
                   for d in D}

dump_production = {d:
                   m.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[j,k,t] for j in Jobs for k in K for t in T if j[DUMP] == d)
                                              >= data["dumps"][d]["desired_throughput"])
                   for d in D}

shovel_capacity = {s:
                   m.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[j,k,t] for j in Jobs for k in K for t in T if j[SOURCE] == s)
                                              <= data["shovels"][s]["processing_capacity"])
                   for s in S}

shovel_use = {s:
              m.addConstr(gp.quicksum(X[j,k,t] * data["loading_time_min"] for j in Jobs for k in K for t in T if j[SOURCE] == s)
                                         <= data["shift_duration_hours"] * MINS_PER_HOUR)
              for s in S}

dump_use = {d:
            m.addConstr(gp.quicksum(X[j,k,t] * data["unloading_time_min"] for j in Jobs for k in K for t in T if j[DUMP] == d)
                                       <= data["shift_duration_hours"] * MINS_PER_HOUR)
            for d in D}

task_duration = {t:
                 m.addConstr(gp.quicksum(X[j,k,t] * Jobs[j] for j in Jobs for k in K)
                             <= data["shift_duration_hours"] * MINS_PER_HOUR)
                for t in T}

flow_at_shovel = {(s,k,t):
                  m.addConstr(gp.quicksum(X[j,k-1,t] for j in Jobs if j != NULL_JOB and j[DEST] == s) <=
                              gp.quicksum(X[j,k,t] for j in Jobs if j != NULL_JOB and j[SOURCE] == s) + X[NULL_JOB,k,t])
                  for s in S for k in K for t in T if k > 0}

do_nothing_when_done = {(k,t):
                        m.addConstr(X[NULL_JOB,k-1,t] <= X[NULL_JOB,k,t])
                        for k in K for t in T if k > 0}

m.setObjective(
    gp.quicksum(data["revenue_per_ton"] * data["truck_capacity_tons"] * X[j,k,t] for j in Jobs for k in K for t in T) - 
    gp.quicksum(((data["distance_matrix"][j[SOURCE]][j[DUMP]] + data["distance_matrix"][j[DEST]][j[DUMP]]) / 1000) * 
                (X[j,k,t] * (data["cost_loaded_per_m"] + data["fixed_cost_loaded_per_m"])) for j in Jobs for k in K for t in T), gp.GRB.MAXIMIZE)

m.optimize()

for t in T:
    print(f"--- Truck {t+1} ---")
    for k in K:
        for j in Jobs:
            if round(X[j,k,t].x) == 1:
                if j == NULL_JOB:
                    print(f"Truck is idle")
                else:
                    print(f'Job {k+1}: Shovel {data["shovels"][j[SOURCE]]["id"]} -> Dump {data["dumps"][j[DUMP]]["id"]} -> Shovel {data["shovels"][j[DEST]]["id"]}')
