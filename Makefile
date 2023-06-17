name=aii_admin_backend
tag=retrieval_plugin_test4
container_name=retrieval_plugin
run:
	docker run --network host --env-file /etc/aii/retrieval_plugin.env --name $(container_name) -d  $(name):$(tag)
run_prod:
	docker run --restart always --network host --name retrieval_plugin --env-file /etc/aii/retrieval_plugin.env -d dextr/aii_admin_backend:retrieval_plugin_test4
build:
	docker build -t $(name):$(tag) .
stop:
	docker stop $(container_name)
rm:
	docker rm $(container_name)
push:
	docker tag $(name):$(tag) dextr/$(name):$(tag) && docker push dextr/$(name):$(tag)
update:
	make build && make push
rerun:
	make build && make stop && make rm && make run
