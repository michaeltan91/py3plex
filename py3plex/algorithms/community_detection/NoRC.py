### ncd

import networkx as nx
import numpy as np
import tqdm
from sklearn.cluster import AffinityPropagation
import multiprocessing as mp
from node_ranking import sparse_page_rank,modularity,stochastic_normalization
from scipy.cluster.hierarchy import dendrogram, linkage
from scipy.cluster.hierarchy import fcluster
import scipy.sparse as sp
from collections import defaultdict
from itertools import product
import community
from networkx.algorithms.community import LFR_benchmark_graph
from sklearn.cluster import AffinityPropagation,DBSCAN,MiniBatchKMeans
from scipy import cluster
from scipy.spatial.distance import pdist
global _RANK_GRAPH

def page_rank_kernel(index_row):

    ## call as results = p.map(pr_kernel, batch)
    pr = sparse_page_rank(_RANK_GRAPH, [index_row],
                          epsilon=1e-6,
                          max_steps=100000,
                          damping=0.90,
                          spread_step=10,
                          spread_percent=0.1,
                          try_shrink=True)
    
    norm = np.linalg.norm(pr, 2)
    if norm > 0:
        pr = pr / np.linalg.norm(pr, 2)
        return (index_row,pr)
    else:
        return (index_row,np.zeros(G.shape[1]))

def create_tree(centers):
    clusters = {}
    to_merge = linkage(centers, method='single')
    for i, merge in enumerate(to_merge):
        if merge[0] <= len(to_merge):
            # if it is an original point read it from the centers array
            a = centers[int(merge[0]) - 1]
        else:
            # other wise read the cluster that has been created
            a = clusters[int(merge[0])]

        if merge[1] <= len(to_merge):
            b = centers[int(merge[1]) - 1]
        else:
            b = clusters[int(merge[1])]
        # the clusters are 1-indexed by scipy
        clusters[1 + i + len(to_merge)] = {
            'children' : [a, b]
        }
        # ^ you could optionally store other info here (e.g distances)
    return clusters

def NoRC_communities(input_graph,clustering_scheme="hierarchical",max_com_num=100,verbose=False,sparisfy=True):
    if verbose:
        print("Walking..")
    global _RANK_GRAPH
    _RANK_GRAPH = input_graph
    A = _RANK_GRAPH.copy()
    _RANK_GRAPH = nx.to_scipy_sparse_matrix(_RANK_GRAPH)
    _RANK_GRAPH = stochastic_normalization(_RANK_GRAPH) ## normalize
    n = _RANK_GRAPH.shape[1]
    with mp.Pool(processes=mp.cpu_count()) as p:
        results = p.map(page_rank_kernel,range(n))
    vectors = np.zeros((n, n))
    for pr_vector in tqdm.tqdm(results):
        if pr_vector != None:
            vectors[pr_vector[0],:] = pr_vector[1]
    vectors = np.nan_to_num(vectors)
    mx_opt = 0
    community_range = np.arange(1,300,3)
    if clustering_scheme == "kmeans":
        if verbose:
            print("Doing kmeans search")
        for nclust in tqdm.tqdm(community_range):
            dx_hc = defaultdict(list)
            clustering_algorithm = MiniBatchKMeans(n_clusters=nclust)
            clusters = clustering_algorithm.fit_predict(vectors)
            for a, b in zip(clusters,A.nodes()):
                dx_hc[a].append(b)
            partitions = dx_hc.values()
            mx = modularity(A, partitions, weight='weight')
            if mx > mx_opt:
                if verbose:
                    print("Improved modularity: {}, found {} communities.".format(mx,len(partitions)))
                mx_opt = mx
                opt_clust = dx_hc
                if mx == 1:
                    return opt_clust
        return opt_clust

    if clustering_scheme == "hierarchical":
        if verbose:
            print("Doing hierarchical clustering")
        Z = linkage(vectors, 'ward')
        mod_hc_opt = 0
        for nclust in tqdm.tqdm(community_range):
            dx_hc = defaultdict(list)
            try:
                cls = fcluster(Z, nclust, criterion='maxclust')
                for a,b in zip(cls,A.nodes()):
                    dx_hc[a].append(b)
                partition_hi = dx_hc.values()
                mod = modularity(A, partition_hi, weight='weight')
                if mod > mod_hc_opt:
                    if verbose:
                        print("Improved modularity: {}, communities: {}".format(mod, len(partition_hi)))
                        
                    mod_hc_opt = mod
                    opt_clust = dx_hc
                    if mod == 1:
                        return opt_clust
            except Exception as es:
                print (es)
        return opt_clust
    
if __name__ == "__main__":

    # n = 50
    # tau1 = 4
    # tau2 = 1.5
    # mu = 0.1
    # graph = LFR_benchmark_graph(n,
    #                             tau1,
    #                             tau2,
    #                             mu,
    #                             average_degree=5,
    #                             min_community=30,
    #                             seed=10)
    
    graph = nx.powerlaw_cluster_graph(10000,3,0.1)
    print(nx.info(graph))
#    communities = NoRC_communities(graph,verbose=True,clustering_scheme="kmeans")
    communities1 = NoRC_communities(graph,verbose=True,clustering_scheme="hierarchical")