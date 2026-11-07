
Total Druft is stored as 

typedef struct{
    image_params
    static_zernike_distribution
} Total_Drift_Struct_5x13
where target lens state is also saved with same data struct

typedef target_lens_state_Type Total_Drift_Struct_5x13

var Total_Drift_Struct_5x13 total_drift 
var target_lens_state_Type target_lens_state



where 
static zerinke distribution is as 
#DEFINE ZERN_ARRAY_LENGHT 101
#DEFINE QGRID_X 13
#DEFINE QGRID_Y 5
{
double na
double zd [5][ZERN_ARRAY_LENGHT]
int len 
}zernike_distribution

{
    zernike_distribution y [13]
}static_zernike_distribution


inline control Sensor references are stored as
#define max_num_of_field+_points 7
#define max_number_of_marks 25
#number_of_odd_filed_points 7
#number_of_even_filed_points 6
#number_of_edge_filed_points 2

typdef xyvect{
    double x
    double y
}

#Define zernike_aaray_lenght 101
typedef zernike_vector double[zernike_aaray_lenght]



typedef 
{
    zernike_vector array
    int len,
    double na
}Zernike_struct

typdef struct{
    xyvect nominal_position,
    xyvect delta_position,
    Zernike_struct dz

}IM_SENS_MARK_DATA

typedef struct{
    IM_SENS_MARK_DATA mark[7]
}scan_measurement
#DEINE MAX_SCANS_IN_LAYOUT 20
#DEINE NUMBER_OF_SCAN_MEAS 30
typedef struct{
    scan_measurement scan_meas[NUMBER_OF_SCAN_MEAS]
}layout_measurement

#MAX_ZERNIKE_ORDER 4 (starts from 0)
typedef double Zernike_Polynoimials[ZERN_ARRAY_LENGHT][] (101x4)

var layout_references sensor_references 
Note: sensor refrences will be used to measure the drift wrt this references

var layout_references reference_scans 

var Zernike_Polynoimials sensor_drift_references 
var sensor_drift 