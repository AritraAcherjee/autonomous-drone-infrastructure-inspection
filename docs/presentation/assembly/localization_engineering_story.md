# Localization Engineering Decision Story

## Current presentation-safe status

Primary localization approach:

**OpenVINS Mono + IMU**

Current OpenVINS status:

- built and integrated;
- sensor delivery validated;
- runtime initialization remained blocked after controlled diagnosis;
- removed from the Stop-B critical path.

Active Stop-B fallback:

**RTAB-Map RGB-D + IMU**

Current RTAB-Map runtime result:

**PENDING**

## Engineering narrative

1. OpenVINS was selected as the primary visual-inertial backend.

2. Compatibility and build integration succeeded.

3. Live initialization did not succeed.

4. The initialization condition was instrumented so diagnosis could use the
   exact OpenVINS initialization statistic rather than guesswork.

5. One evidence-derived correction was tested.

6. Initialization remained blocked.

7. Additional blind tuning was rejected because it would reduce scientific
   defensibility without evidence that another parameter change addressed
   the root condition.

8. The pre-designed RTAB-Map RGB-D + IMU fallback was activated for the
   Stop-B critical path.

9. The downstream localization interface/contract was kept stable so the
   fallback does not require redesigning every downstream subsystem.

10. OpenVINS is preserved as a post-Stop-B improvement effort rather than
    being misrepresented as successful runtime odometry.

## Interview framing

This is useful as an engineering-decision example because the project:

- defined a primary and fallback architecture before failure;
- gathered diagnostic evidence;
- tested a bounded correction;
- used a stop condition instead of indefinite tuning;
- preserved subsystem contracts;
- redirected effort toward the delivery-critical path.

## Prohibited wording

Do not say:

- OpenVINS successfully tracked the moving drone;
- OpenVINS provided verified odometry;
- RTAB-Map localization is successful;
- real ATE or RPE has been measured.

Until accepted MSI/P19 evidence exists, those fields remain:

**PENDING**
