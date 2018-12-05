# test functions

import numpy as np
from data_linking_functions import calc_correlation_matrix

def test_calc_correlation_matrix():
    # Test with simple input matrices and known outcome
    A = np.array([[0, 0, 0, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 0, 1], [0, 0, 0, 1]])
    B = np.array([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
    M_A_B, M_A_notB, M_notA_B, M_notA_notB = calc_correlation_matrix(A, B)
    assert M_A_B[1][2] == 1    
    assert M_A_notB[2][1] == 2 
    assert M_A_notB[2][2] == 1 
    assert M_notA_B[4][0] == 2
    assert M_notA_B[1][2] == 0
    assert np.max([M_A_B, M_A_notB, M_notA_B]) == 2  # in this example
    assert np.max(M_notA_notB) == 3
    assert np.max(M_notA_notB == np.array([[1, 2, 2, 2, 2, 3],
                                   [0, 1, 2, 1, 1, 2],
                                   [0, 1, 2, 1, 1, 2],
                                   [1, 2, 2, 2, 2, 3],
                                   [1, 2, 2, 2, 2, 3]]))


from data_linking_functions import calc_likelihood_matrix
    
def test_calc_likelihood_matrix():
    # Test with simple input matrices and known outcome
    A = np.array([[0, 0, 0, 1], [0, 0, 1, 1], [0, 0, 1, 1], [0, 0, 0, 1], [0, 0, 0, 1]])
    B = np.array([[1, 1, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 1, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1]])
    M_A_B, M_A_notB, M_notA_B, M_notA_notB = calc_correlation_matrix(A, B)
    LBA, LBnotA, LAB, LAnotB = calc_likelihood_matrix(A, B,M_A_B, M_A_notB, M_notA_B)
    assert np.max([LBA, LBnotA, LAB, LAnotB]) <= 1  # no likelihood can be > 1
    assert LBA[1][2] == 0.5
    assert LAB[1][2] == 1
    assert LBnotA[1][2] == 0
    assert LBnotA[1][0] == 1
    assert LAnotB[1][0] == 1
    assert LAnotB[4][4] == 1/3
    assert LBA.shape == (len(A), len(B))  # must have shape len(A), len(B)


from data_linking_functions import pair_prob
    
def test_pair_prob():
    # Test pair_prob with known cases
    assert pair_prob(1, 100, 1, 1) == 1/100  
    assert pair_prob(1, 100, 50, 1) == 0.5
    assert pair_prob(1, 100, 1, 50) == 0.5
    assert pair_prob(1, 100, 2, 2) == 98/100 * 2/99 + 2/100 * 98/99
    
    
from data_linking_functions import hit_prob_dist

def test_hit_prob_dist():
    # Testhit_prob_dist with known cases
    
    pks = hit_prob_dist(100, 1, 1, 100)
    assert np.sum(pks) > 0.99999999
    assert np.sum(pks) < 1.00000001
    assert pks[0][0] == 0.99**100
    
    