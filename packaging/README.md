# Quiver packaging

## OpenShift

A docker image and OpenShift Container Platform (OCP) template are
provided under the openshift directory.  The
'openshift-support-template.yml' template provides a BuildConfig which
allows you to build from source.

To deploy this template, you can run the below:

    oc process -f openshift/openshift-support-template.yml | oc create -f -
    
The second template, 'openshift-pod-template.yml', deploys a runnable
quiver. It requires several parameters to run correctly:

 - DOCKER_IMAGE - the location of the fully qualified docker pull URL
 - DOCKER_CMD - the quiver command, in JSON array format, you want to execute

For example:

    oc process -f openshift/openshift-pod-template.yml \
        DOCKER_IMAGE=172.30.235.81:5000/test/quiver:latest \
        DOCKER_CMD="[\"quiver\", \"//172.17.0.7:5673/jobs/test\", \"--verbose\"]" \
        | oc create -f -
