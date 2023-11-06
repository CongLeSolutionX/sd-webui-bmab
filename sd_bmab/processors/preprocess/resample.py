from PIL import Image

from modules import shared
from modules import devices
from modules import images

from sd_bmab import util
from sd_bmab import constants
from sd_bmab.util import debug_print
from sd_bmab.base import process_txt2img, Context, ProcessorBase
from sd_bmab.processors.controlnet import LineartNoise


class ResamplePreprocessor(ProcessorBase):
	def __init__(self) -> None:
		super().__init__()

		self.resample_opt = {}
		self.enabled = False
		self.save_image = False
		self.checkpoint = None
		self.vae = None
		self.prompt = None
		self.negative_prompt = None
		self.sampler = None
		self.upscaler = None
		self.steps = 20
		self.cfg_scale = 0.7
		self.denoising_strength = 0.75
		self.strength = 0.5
		self.begin = 0.0
		self.end = 1.0

		self.base_sd_model = None

	def preprocess(self, context: Context, image: Image):
		self.enabled = context.args['resample_enabled']
		self.resample_opt = context.args.get('module_config', {}).get('resample_opt', {})

		self.save_image = self.resample_opt.get('save_image', self.save_image)
		self.checkpoint = self.resample_opt.get('checkpoint', self.checkpoint)
		self.vae = self.resample_opt.get('vae', self.vae)
		self.prompt = self.resample_opt.get('prompt', self.prompt)
		self.negative_prompt = self.resample_opt.get('negative_prompt', self.negative_prompt)
		self.sampler = self.resample_opt.get('sampler', self.sampler)
		self.upscaler = self.resample_opt.get('upscaler', self.upscaler)
		self.steps = self.resample_opt.get('steps', self.steps)
		self.cfg_scale = self.resample_opt.get('cfg_scale', self.cfg_scale)
		self.denoising_strength = self.resample_opt.get('denoising_strength', self.denoising_strength)
		self.strength = self.resample_opt.get('scale', self.strength)
		self.begin = self.resample_opt.get('width', self.begin)
		self.end = self.resample_opt.get('height', self.end)

		return self.enabled

	@staticmethod
	def get_resample_args(image, weight, begin, end):
		cn_args = {
			'input_image': util.b64_encoding(image),
			'model': shared.opts.bmab_cn_tile_resample,
			'weight': weight,
			"guidance_start": begin,
			"guidance_end": end,
			'resize mode': 'Just Resize',
			'allow preview': False,
			'pixel perfect': False,
			'control mode': 'ControlNet is more important',
			'processor_res': 512,
			'threshold_a': 64,
			'threshold_b': 64,
		}
		return cn_args

	def process(self, context: Context, image: Image):

		if self.checkpoint != constants.checkpoint_default or self.vae != constants.vae_default:
			context.save_and_apply_checkpoint(self.checkpoint, self.vae)

		if self.prompt == '':
			self.prompt = context.get_prompt_by_index()
			debug_print('prompt', self.prompt)
		elif self.prompt.find('#!org!#') >= 0:
			current_prompt = context.get_prompt_by_index()
			self.prompt = self.prompt.replace('#!org!#', current_prompt)
			print('Prompt', self.prompt)
		if self.negative_prompt == '':
			self.negative_prompt = context.sdprocessing.negative_prompt
		if self.checkpoint == constants.checkpoint_default:
			self.checkpoint = context.sdprocessing.sd_model
		if self.sampler == constants.sampler_default:
			self.sampler = context.sdprocessing.sampler_name

		seed, subseed = context.get_seeds()
		options = dict(
			seed=seed, subseed=subseed,
			denoising_strength=self.denoising_strength,
			prompt=self.prompt,
			negative_prompt=self.negative_prompt,
			sampler_name=self.sampler,
			steps=self.steps,
			cfg_scale=self.cfg_scale,
		)
		context.add_job()
		if self.save_image:
			saved = image.copy()
			images.save_image(
				saved, context.sdprocessing.outpath_samples, '',
				context.sdprocessing.all_seeds[context.index], context.sdprocessing.all_prompts[context.index],
				shared.opts.samples_format, p=context.sdprocessing, suffix='-before-resample')
			context.add_extra_image(saved)
		cn_op_arg = self.get_resample_args(image, self.strength, self.begin, self.end)
		result = process_txt2img(context.sdprocessing, options=options, controlnet=cn_op_arg)
		return result

	def postprocess(self, context: Context, image: Image):
		devices.torch_gc()

