"""Compile a two-stage Kubeflow pipeline: tracked training then a quality gate."""

from kfp import compiler, dsl


def compile_pipeline(image, destination, source_revision="uncommitted"):
    @dsl.container_component
    def train(execution: str, result: dsl.OutputPath(str)):
        return dsl.ContainerSpec(
            image=image,
            command=["python", "-m", "mlops_platform.pipeline_worker"],
            args=[
                "train",
                "--execution",
                execution,
                "--output",
                result,
                "--source-revision",
                source_revision,
                "--image",
                image,
            ],
        )

    @dsl.container_component
    def approve(result: str, minimum_accuracy: float, run_id: dsl.OutputPath(str)):
        return dsl.ContainerSpec(
            image=image,
            command=["python", "-m", "mlops_platform.pipeline_worker"],
            args=[
                "approve",
                "--result",
                result,
                "--threshold",
                minimum_accuracy,
                "--output",
                run_id,
            ],
        )

    @dsl.pipeline(name="tracked-iris-training")
    def workflow(execution: str, minimum_accuracy: float = 0.8):
        training = train(execution=execution).set_caching_options(False)
        training.set_cpu_request("100m").set_memory_request("256Mi").set_memory_limit("768Mi")
        approve(
            result=training.outputs["result"], minimum_accuracy=minimum_accuracy
        ).set_caching_options(False)

    compiler.Compiler().compile(pipeline_func=workflow, package_path=str(destination))
