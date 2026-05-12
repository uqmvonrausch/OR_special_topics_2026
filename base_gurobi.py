import json
import gurobipy as gp
from enum import Enum

with open("./data/scenario_1.json") as data_file:
    data = json.load(data_file)

MINS_PER_HOUR = 60

# OBJ1_WEIGHT = 1/20642.60
# OBJ2_WEIGHT = 1/(17.44 * MINS_PER_HOUR)
# OBJ3_WEIGHT = 1/(8.55 * MINS_PER_HOUR)
OBJ1_WEIGHT = 1
OBJ2_WEIGHT = 1
OBJ3_WEIGHT = 1

class TruckState(Enum):
    LOADED = 1
    UNLOADED = 2

S = range(len(data["shovels"]))
D = range(len(data["dumps"]))
T = range(data["n_trucks"])

allocation_model = gp.Model()

X = {(i,j,t): 
     allocation_model.addVar(vtype=gp.GRB.INTEGER, name="X_{i},{j},{t}")
     for i in S for j in D for t in T}

Y = {(j,i,t): 
     allocation_model.addVar(vtype=gp.GRB.INTEGER, name="Y_{j},{i},{t}")
     for i in S for j in D for t in T}

dump_capacity = {j:
                   allocation_model.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[i,j,t] for i in S for t in T)
                                              <= data["dumps"][j]["processing_capacity"])
                   for j in D}

dump_production = {j:
                   allocation_model.addConstr(gp.quicksum(data["truck_capacity_tons"] * X[i,j,t] for i in S for t in T)
                                              >= data["dumps"][j]["desired_throughput"])
                   for j in D}

shovel_capacity = {i:
                   allocation_model.addConstr(gp.quicksum(data["truck_capacity_tons"] * Y[j,i,t] for j in D for t in T)
                                              <= data["shovels"][i]["processing_capacity"])
                   for i in S}

shovel_use = {i:
              allocation_model.addConstr(gp.quicksum(Y[j,i,t] * data["loading_time_min"] for j in D for t in T)
                                         <= data["shift_duration_hours"] * MINS_PER_HOUR)
              for i in S}

dump_use = {j:
            allocation_model.addConstr(gp.quicksum(X[i,j,t] * data["unloading_time_min"] for i in S for t in T)
                                       <= data["shift_duration_hours"] * MINS_PER_HOUR)
            for j in D}

def calc_task_duration(shovel_idx: int, dump_idx: int, state: TruckState):
    
    speed_kph = data["speed_loaded_kph"] if state == TruckState.LOADED else data["speed_unloaded_kph"]
    distance_m = data["distance_matrix"][shovel_idx][dump_idx]

    operation_time_min = data["unloading_time_min"] if state == TruckState.LOADED else data["loading_time_min"]

    return (distance_m / speed_kph) * MINS_PER_HOUR / 1000 + operation_time_min

for i in [f"Shovel {i} to dump {j}: {calc_task_duration(i,j,l)}\n" for i in S for j in D for l in [TruckState.LOADED, TruckState.UNLOADED]]:
    print(i)

task_duration = {t:
                 allocation_model.addConstr(gp.quicksum(X[i,j,t] * calc_task_duration(i,j,TruckState.LOADED) +
                                                        Y[j,i,t] * calc_task_duration(i,j,TruckState.UNLOADED)
                                                        for i in S for j in D)
                                            <= data["shift_duration_hours"] * MINS_PER_HOUR)
                 for t in T}

flow_at_shovel = {i:
                  allocation_model.addConstr(gp.quicksum(X[i,j,t] for j in D for t in T)
                                             == gp.quicksum(Y[j,i,t] for j in D for t in T))
                  for i in S}

flow_at_dump = {j:
                  allocation_model.addConstr(gp.quicksum(X[i,j,t] for i in S for t in T)
                                             == gp.quicksum(Y[j,i,t] for i in S for t in T))
                  for j in D}

allocation_model.setObjective(
    OBJ1_WEIGHT * gp.quicksum((data["distance_matrix"][i][j] / 1000) * (X[i,j,t] * (data["cost_loaded_per_m"] + data["fixed_cost_loaded_per_m"]) +
                                                               Y[j,i,t] * (data["cost_unloaded_per_m"] + data["fixed_cost_unloaded_per_m"]))
                                                               for i in S for j in D for t in T) #+
    # OBJ2_WEIGHT * gp.quicksum(data["shift_duration_hours"] * MINS_PER_HOUR -
    #                           gp.quicksum(X[i,j,t] * calc_task_duration(i,j,TruckState.LOADED) +
    #                                       Y[j,i,t] * calc_task_duration(i,j,TruckState.UNLOADED)
    #                                         for i in S for j in D)
    #                           for t in T)# +
    # OBJ3_WEIGHT * gp.quicksum(data["shift_duration_hours"] * MINS_PER_HOUR -
    #                           gp.quicksum(Y[j,i,t] * data["loading_time_min"]
    #                                       for j in D for t in T)
    #                           for i in S)
                              , gp.GRB.MINIMIZE)
                
allocation_model.optimize()

for t in T:
    print(f"--- Truck {t+1} ---")
    loaded_jobs = [(data["shovels"][i]["id"], data["dumps"][j]["id"], X[i,j,t].x) for i in S for j in D if round(X[i,j,t].x)>=1]
    unloaded_jobs = [(data["dumps"][j]["id"], data["shovels"][i]["id"], Y[j,i,t].x) for i in S for j in D if round(Y[j,i,t].x)>=1]

    print(f"Loaded Jobs:")
    print(loaded_jobs)
    print(f"Unloaded Jobs:")
    print(unloaded_jobs)