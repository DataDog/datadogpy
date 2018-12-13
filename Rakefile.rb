require 'tmpdir'
require 'json'

task :clean => [:clean_pyc, :clean_build, :clean_dist]

task :clean_pyc do
  sh "find . -name '*.pyc' -exec rm {} \\;"
end

task :clean_build do
  sh "rm -rf build/*"
end

task :clean_dist do
  sh "rm -f dist/*.egg"
end

task :doc do
  sh "python setup.py build_sphinx"
end


task :release do
  sh "python setup.py sdist upload"
end


LayerUtils = Struct.new(:python_version_number, :layer_name, :zip_name, :pip_package) do
  def dockerfile
    %{FROM python:#{python_version_number}
RUN mkdir -p /usr/layer_build/python/lib/python#{python_version_number}/site-packages
WORKDIR /usr/layer_build
RUN pip install #{pip_package} -t ./python/lib/python#{python_version_number}/site-packages}
  end
end

# Shared layer information: the name and destination of each version.
# Note that the `pip_package` variable gets chosen by the tasks.
LAYER_INFOS = [LayerUtils.new("2.7", "Datadog-Python27-metric", "datadogpy27.zip"),
               LayerUtils.new("3.6", "Datadog-Python36-metric", "datadogpy36.zip"),
               LayerUtils.new("3.7", "Datadog-Python37-metric", "datadogpy37.zip")]

task :build_layer_zips do
  LAYER_INFOS.each do |layer|
    puts layer
    # Build layer from PIP_TARGET (master latest commit by default)
    layer.pip_package = ENV["PIP_TARGET"] || "git+https://github.com/DataDog/datadogpy"

    # Create a temp dir to extract the built files
    Dir.mktmpdir do |dir|

      # Build the docker image, with empty context
      sh "(cd #{dir}; echo '#{layer.dockerfile}' | docker build -t datadogpy_image -)"

      # Pipe the archived `python` directory which contains the pip install from the container,
      # and extract the tar's files on the host
      sh "docker run datadogpy_image tar cf - python | tar -xf - -C #{dir}"

      # Zip the extracted files
      sh "mkdir -p layers"
      pwd = Dir.pwd
      sh "(cd #{dir} && zip -q -r #{pwd}/layers/#{layer.zip_name} ./)"
    end
  end
end

task :publish_layer do
  REGIONS = ['us-east-2', 'us-east-1', 'us-west-1', 'us-west-2', 'ap-south-1',
             'ap-northeast-3', 'ap-northeast-2', 'ap-southeast-1', 'ap-southeast-2',
             'ap-northeast-1', 'ca-central-1', 'cn-north-1', 'cn-northwest-1',
             'eu-central-1', 'eu-west-1', 'eu-west-2', 'eu-west-3', 'sa-east-1']
  REGIONS.each do |region|
    LAYER_INFOS.each do |layer|
      puts "====== Starting publishing in region #{region}, layer: #{layer} ====="
      aws_cli_command = "aws lambda publish-layer-version --layer-name #{layer.layer_name} \
                      --description 'Datadog python API client for lambdas' \
                      --zip-file fileb://layers/#{layer.zip_name} --region #{region} \
                      --compatible-runtimes python#{layer.python_version_number}"
      puts aws_cli_command
      aws_cli_output = `#{aws_cli_command}`
      puts aws_cli_output

      version_number = JSON.parse(aws_cli_output)['Version']
      puts "Found version number: #{version_number}. Adding permissions..."

      aws_cli_command = "aws lambda add-layer-version-permission --layer-name #{layer.layer_name} \
        --version-number #{version_number} \
        --statement-id 'release-#{version_number}' \
        --action lambda:GetLayerVersion --principal '*' \
        --region #{region}"
      puts aws_cli_command
      aws_cli_output = `#{aws_cli_command}`
      puts aws_cli_output
      puts ">>>>>> Done publishing in region #{region}, layer: #{layer} ! <<<<<"
    end
  end
end
