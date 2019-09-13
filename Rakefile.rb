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
  sh "python setup.py sdist bdist_wheel --universal upload"
end
